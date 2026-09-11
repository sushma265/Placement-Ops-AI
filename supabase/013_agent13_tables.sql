-- ============================================================
-- Agent 13 — Canonical Tables & RLS Policies (Phase 1)
-- ============================================================

-- Safely extend the `public.profiles` role CHECK constraint to include faculty, hod, principal
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_role_check;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check 
    CHECK (role IN ('student', 'recruiter', 'tpo', 'faculty', 'hod', 'principal'));

-- Create schemas if they do not exist
CREATE SCHEMA IF NOT EXISTS studentlife;
CREATE SCHEMA IF NOT EXISTS curriculum;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS agentops;
CREATE SCHEMA IF NOT EXISTS people;

-- ============================================================
-- STUDENTLIFE
-- ============================================================
CREATE TABLE IF NOT EXISTS studentlife.student_interest (
    student_interest_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id int NOT NULL, -- FK to public.students(id) handled in SQLAlchemy
    area text NOT NULL,
    declared_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS studentlife.resume_claim (
    claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id int NOT NULL,
    claim_type text NOT NULL,
    description text NOT NULL,
    domain text NOT NULL,
    verification_status text NOT NULL DEFAULT 'PENDING' 
        CHECK (verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'UNVERIFIABLE')),
    promoted_to_achievement_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- CURRICULUM
-- ============================================================
CREATE TABLE IF NOT EXISTS curriculum.course_domain_tag (
    course_id text PRIMARY KEY,
    domain text NOT NULL 
        CHECK (domain IN ('TECHNICAL', 'RESEARCH', 'INNOVATION', 'COMMUNICATION', 'DESIGN')),
    weight numeric(3,2) NOT NULL DEFAULT 1.0
);

-- ============================================================
-- PEOPLE
-- ============================================================
CREATE TABLE IF NOT EXISTS people.faculty_expertise (
    faculty_id int PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    profile_id uuid NOT NULL UNIQUE, -- FK to public.profiles
    name text NOT NULL,
    department text NOT NULL,
    research_areas text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- RESEARCH
-- ============================================================
CREATE TABLE IF NOT EXISTS research.project (
    project_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id int NOT NULL REFERENCES people.faculty_expertise(faculty_id),
    title text NOT NULL,
    description text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE' 
        CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    capacity int NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research.project_requirement (
    requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES research.project(project_id) ON DELETE CASCADE,
    domain text,
    skill text,
    min_score numeric NOT NULL DEFAULT 0,
    is_required boolean NOT NULL DEFAULT true,
    weight numeric(3,2) NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS research.project_member (
    membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES research.project(project_id) ON DELETE CASCADE,
    student_id int NOT NULL,
    role text NOT NULL DEFAULT 'RESEARCH_ASSISTANT',
    status text NOT NULL DEFAULT 'ACTIVE',
    assigned_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- AGENTOPS
-- ============================================================
CREATE TABLE IF NOT EXISTS agentops.agent_run (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_code text NOT NULL DEFAULT 'A13_FAST_LEARNER',
    triggered_by uuid NOT NULL, -- profile_id
    status text NOT NULL DEFAULT 'STARTED',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agentops.agent_run_input (
    input_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES agentops.agent_run(run_id) ON DELETE CASCADE,
    context_snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agentops.agent_output (
    output_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES agentops.agent_run(run_id) ON DELETE CASCADE,
    subject_type text NOT NULL DEFAULT 'STUDENT',
    subject_id int NOT NULL,
    payload jsonb NOT NULL,
    reasoning_summary text NOT NULL,
    confidence numeric NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agentops.human_review (
    review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    output_id uuid NOT NULL REFERENCES agentops.agent_output(output_id) ON DELETE CASCADE,
    decision text NOT NULL DEFAULT 'PENDING'
        CHECK (decision IN ('PENDING', 'APPROVED', 'MODIFY', 'REJECTED')),
    reviewed_by uuid, -- profile_id
    reviewed_at timestamptz,
    comments text
);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
ALTER TABLE agentops.agent_output ENABLE ROW LEVEL SECURITY;
ALTER TABLE agentops.agent_output FORCE ROW LEVEL SECURITY;

ALTER TABLE agentops.human_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE agentops.human_review FORCE ROW LEVEL SECURITY;

-- Policy mappings for outputs and reviews
-- Student can see their own output
CREATE POLICY output_student_select ON agentops.agent_output FOR SELECT USING (
    subject_type = 'STUDENT' AND subject_id IN (
        SELECT id FROM public.students WHERE profile_id = auth.uid()::text
    )
);

-- Faculty/HOD/Principal can see outputs in scope
-- (For Phase 1, we allow read if they have faculty/hod/principal/tpo role in profile_roles)
CREATE POLICY output_leadership_select ON agentops.agent_output FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.profile_roles 
        WHERE profile_id = auth.uid()::text 
        AND role IN ('faculty', 'hod', 'principal', 'tpo')
    )
);

-- Review access (Read)
CREATE POLICY review_student_select ON agentops.human_review FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM agentops.agent_output o 
        JOIN public.students s ON o.subject_id = s.id 
        WHERE o.output_id = agentops.human_review.output_id 
        AND s.profile_id = auth.uid()::text
    )
);

CREATE POLICY review_leadership_select ON agentops.human_review FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.profile_roles 
        WHERE profile_id = auth.uid()::text 
        AND role IN ('faculty', 'hod', 'principal', 'tpo')
    )
);

-- Review access (Write: Update decision)
CREATE POLICY review_leadership_update ON agentops.human_review FOR UPDATE USING (
    EXISTS (
        SELECT 1 FROM public.profile_roles 
        WHERE profile_id = auth.uid()::text 
        AND role IN ('faculty', 'hod', 'principal', 'tpo')
    )
);
