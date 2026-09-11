-- ============================================================
-- Agent 13 — Deterministic SQL Views (Phase 2)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS outcomes;

-- 1. DETERMINISTIC STUDENT STRENGTH PROFILE & GROWTH
-- Calculates: 5-domain scores, Growth (HIGH/MODERATE/LOW), and Hidden Talent
CREATE OR REPLACE VIEW outcomes.v_student_strength_profile AS
WITH resume_agg AS (
    SELECT 
        student_id,
        domain,
        SUM(CASE 
            WHEN verification_status = 'VERIFIED' THEN 100.0 
            WHEN verification_status = 'PENDING' THEN 30.0 
            ELSE 0.0 
        END) as resume_score
    FROM studentlife.resume_claim
    GROUP BY student_id, domain
),
base_scores AS (
    SELECT 
        s.id AS student_id,
        s.branch,
        s.cgpa,
        COALESCE(jsonb_array_length(NULLIF(s.projects::jsonb, 'null'::jsonb)), 0) AS project_count,
        COALESCE(jsonb_array_length(NULLIF(s.hackathons::jsonb, 'null'::jsonb)), 0) AS hackathon_count,
        COALESCE(jsonb_array_length(NULLIF(s.certifications::jsonb, 'null'::jsonb)), 0) AS cert_count,
        COALESCE(s.api_score, s.cgpa * 10) AS api_score,
        COALESCE(s.ssi_score, 0) AS ssi_score
    FROM public.students s
),
domain_scores AS (
    SELECT 
        b.student_id,
        b.branch,
        b.cgpa,
        d.domain,
        -- Academic Component (Normalized to 100)
        LEAST(b.api_score, 100.0) AS academic_component,
        -- Achievement Component
        LEAST((b.project_count * 15.0) + (b.hackathon_count * 20.0) + b.ssi_score, 100.0) AS achievement_component,
        -- Certification Component
        LEAST(b.cert_count * 25.0, 100.0) AS certification_component,
        -- Resume Component
        LEAST(COALESCE(r.resume_score, 0.0), 100.0) AS resume_component
    FROM base_scores b
    CROSS JOIN (VALUES ('TECHNICAL'), ('RESEARCH'), ('INNOVATION'), ('COMMUNICATION'), ('DESIGN')) AS d(domain)
    LEFT JOIN resume_agg r ON b.student_id = r.student_id AND r.domain = d.domain
),
weighted_domain_scores AS (
    SELECT 
        student_id,
        branch,
        cgpa,
        domain,
        -- Frozen Scoring Formula: 0.45*academic + 0.35*achievement + 0.10*cert + 0.10*resume
        ROUND(
            (0.45 * academic_component) + 
            (0.35 * achievement_component) + 
            (0.10 * certification_component) + 
            (0.10 * resume_component), 
        2) AS domain_score
    FROM domain_scores
),
relative_stats AS (
    SELECT 
        branch,
        domain,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY domain_score) AS median_domain_score
    FROM weighted_domain_scores
    GROUP BY branch, domain
),
-- Deduplicate to one row per student for a clean cgpa percentile ranking.
-- weighted_domain_scores has 5 rows per student (one per domain), which would
-- inflate the PERCENT_RANK window.  This CTE collapses to 1 row per student.
student_cgpa_percentiles AS (
    SELECT DISTINCT
        student_id,
        branch,
        cgpa,
        PERCENT_RANK() OVER (PARTITION BY branch ORDER BY cgpa) AS cgpa_percentile
    FROM weighted_domain_scores
),
student_percentiles AS (
    SELECT 
        w.student_id,
        w.branch,
        w.domain,
        scp.cgpa,
        w.domain_score,
        PERCENT_RANK() OVER (PARTITION BY w.branch, w.domain ORDER BY w.domain_score) AS domain_percentile,
        scp.cgpa_percentile
    FROM weighted_domain_scores w
    JOIN student_cgpa_percentiles scp ON w.student_id = scp.student_id
),
growth_baseline AS (
    SELECT 
        id as student_id,
        branch,
        -- Simulated growth rate derived from current indicators
        COALESCE(api_score - (cgpa * 10), 0) AS raw_growth
    FROM public.students
),
growth_percentiles AS (
    SELECT 
        student_id,
        branch,
        PERCENT_RANK() OVER (PARTITION BY branch ORDER BY raw_growth) AS growth_percentile
    FROM growth_baseline
)
SELECT 
    sp.student_id,
    sp.branch,
    sp.domain,
    sp.domain_score,
    sp.cgpa,
    sp.domain_percentile,
    sp.cgpa_percentile,
    -- RELATIVE HIDDEN TALENT DETECTION
    -- max(domain) > batch median + 10 margin AND domain_percentile > cgpa_percentile
    CASE 
        WHEN sp.domain_score > rs.median_domain_score + 10.0 
         AND sp.domain_percentile > sp.cgpa_percentile 
        THEN TRUE 
        ELSE FALSE 
    END AS is_hidden_talent,
    -- RELATIVE HIGH-GROWTH DETECTION
    CASE 
        WHEN gp.growth_percentile >= 0.80 THEN 'HIGH'
        WHEN gp.growth_percentile >= 0.40 THEN 'MODERATE'
        ELSE 'LOW'
    END AS growth_status
FROM student_percentiles sp
JOIN relative_stats rs ON sp.branch = rs.branch AND sp.domain = rs.domain
JOIN growth_percentiles gp ON sp.student_id = gp.student_id;


-- 2. DETERMINISTIC OPPORTUNITY ELIGIBILITY & FIT
-- Evaluates hard eligibility rules and computes fit scores.
CREATE OR REPLACE VIEW outcomes.v_opportunity_eligibility_and_fit AS
WITH hard_requirements AS (
    SELECT 
        project_id,
        domain,
        min_score,
        is_required,
        weight
    FROM research.project_requirement
),
student_req_check AS (
    SELECT 
        s.student_id,
        r.project_id,
        BOOL_AND(
            CASE 
                WHEN r.is_required = TRUE THEN (s.domain_score >= r.min_score)
                ELSE TRUE 
            END
        ) AS is_eligible,
        -- Fit score: weighted average of matching domains
        ROUND(SUM(s.domain_score * r.weight) / NULLIF(SUM(r.weight), 0), 2) AS fit_score
    FROM outcomes.v_student_strength_profile s
    JOIN hard_requirements r ON s.domain = r.domain
    GROUP BY s.student_id, r.project_id
)
SELECT 
    src.student_id,
    src.project_id,
    src.is_eligible,
    src.fit_score
FROM student_req_check src;


-- 3. DETERMINISTIC FACULTY MENTOR COMPATIBILITY
-- Maps student domain strength against faculty capacity and expertise.
CREATE OR REPLACE VIEW outcomes.v_faculty_mentor_compatibility AS
WITH faculty_capacity AS (
    SELECT 
        f.faculty_id,
        f.name AS faculty_name,
        COALESCE(SUM(p.capacity), 0) AS total_capacity,
        COUNT(pm.membership_id) AS current_members
    FROM people.faculty_expertise f
    LEFT JOIN research.project p ON f.faculty_id = p.faculty_id AND p.status = 'ACTIVE'
    LEFT JOIN research.project_member pm ON p.project_id = pm.project_id AND pm.status = 'ACTIVE'
    GROUP BY f.faculty_id, f.name
)
SELECT 
    s.student_id,
    fc.faculty_id,
    fc.faculty_name,
    s.domain_score AS compatibility_score
FROM outcomes.v_student_strength_profile s
CROSS JOIN faculty_capacity fc
WHERE fc.total_capacity > fc.current_members
  AND s.domain_score >= 80.0 -- Ensure strong match threshold
  AND s.domain = 'RESEARCH'; -- Aligning purely with research capabilities for this baseline
