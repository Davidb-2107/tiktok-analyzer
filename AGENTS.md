<claude-mem-context>
# Memory Context

# [TikTok Analyzer] recent context, 2026-06-01 6:54am GMT+2

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (18 895t read) | 213 654t work | 91% savings

### May 31, 2026
5084 10:25a 🔵 refresh-metrics endpoint smoke test passed on real TikTok job
5085 " 🔵 Vite HMR confirmed JobHistory.jsx changes delivered to browser
5089 10:39a 🟣 Refresh Button Added to Frontend
5091 " 🔵 App.jsx Button Row Structure Identified for Refresh Button Placement
5092 " 🔵 App.jsx handleBack Resets All Job State
5094 10:40a 🟣 handleRefreshMetrics Function Added to App.jsx
5097 10:47a 🟣 Refresh Metrics Button Added to TikTok Analyzer UI
S1356 Launch multi-agent workflow to plan + adversarially review 4 TikTok Analyzer frontend features in parallel (Refresh ALL, Open URL, Toast, Backfill tags) (May 31, 10:48 AM)
5109 10:51a 🟣 Refresh ALL Button — Bulk Metrics Re-poll for JobHistory
S1359 TikTok Analyzer — 4 under-the-hour frontend features shipped via multi-agent plan+critique workflow (Refresh ALL, ↗ Source, Toast, Backfill tags/description) (May 31, 10:51 AM)
5113 10:52a 🔵 TikTok Analyzer — Confirmed Component File State and Backend Function Locations
5114 " 🟣 Open URL Feature Plan — "↗ Source" Link in Action Button Row
5116 " 🟣 Toast Feedback System Plan — New Toast.jsx + App.jsx Wiring
5117 " 🟣 Refresh ALL Plan — Sequential Bulk Metrics Refresh with Progress in JobHistory
5118 " 🔵 _refresh_metadata_sync Already Extracts tags and description Fields
5119 10:53a 🟣 Backfill Tags/Description Plan — Docker Exec Python One-liner for All Done Jobs
5120 " ⚖️ Critique Phase — open_url Feature Passes Adversarial Review (PASS)
5121 " ⚖️ Critique Phase — refresh_all Feature Passes Adversarial Review (PASS)
5122 10:54a 🔴 Toast Feature — WARN: Timer-Reset Bug When onDismiss is Inline Arrow Function
5123 " 🔴 Backfill Tags — WARN: Python Version f-string Bug + Missing Rate Limiting
5124 10:55a 🟣 JobHistory.jsx — Refresh ALL + Delete Toast + Failure Counting Applied to File
5125 " 🟣 App.jsx and JobHistory.jsx — Open URL + Refresh All UI Applied to Files
5126 10:56a 🟣 Toast.jsx Created — Bug Fix Applied: useEffect Deps [message] Only
5127 " 🟣 App.jsx Toast Integration — Import, State, showToast Helper, handleRefreshMetrics Error Handling Applied
5128 10:57a 🟣 App.jsx — Toast and Refresh Prop Wiring Complete: JobHistory Gets onRefreshComplete + showToast, Toast Rendered
5129 " 🟣 Backfill Script Written as Proper Python File — Addresses Both Critique Issues
5134 10:58a 🟣 Backfill Script Executed Successfully — 27/31 Jobs Updated, 0 Failures
5135 10:59a 🔵 Post-Deploy Verification — All Features Live: HMR Confirmed, Toast.jsx in Container, Inbox Files Regenerated
S1361 Launch second workflow batch — half-day features: SRT word timestamps, multi-project inbox routing, manual user-tags (May 31, 10:59 AM)
5142 11:01a 🟣 Second Workflow Launched — Half-Day Features: SRT Captions, Multi-Project Routing, User Tags
S1370 Rappel des dernières améliorations restantes à faire sur le projet TikTok Analyzer (May 31, 11:02 AM)
5145 11:02a 🔵 docker-compose.yml and .env Confirmed — SCRIPT_INBOX_HOST Volume Mount Structure for Multi-Project Routing
5148 11:03a 🟣 SRT Captions Feature Plan — Word Timestamps + /captions.srt Endpoint + Frontend Link
5149 " 🟣 User Tags Feature Plan — PATCH /tags Endpoint + Chip UI + Script Header Integration
5151 11:04a 🟣 Multi-Project Routing Feature Plan — 10 Edits Across 5 Files: Inbox Override, AnalyzeRequest, JobResponse, docker-compose, .env, UrlInput, App.jsx
5155 11:05a 🔵 Critique Phase Uniqueness Checks — All SRT Plan old_strings Confirmed as Exactly 1 Match
5156 " ⚖️ Critique Phase — project Feature WARN: Backward Compat Fine, INBOX_ARCHIVE Dead Config, Poll Loop Overwrites State
5158 " ⚖️ Critique Phase — usertags Feature PASS: Cross-Feature Collision Risk on JobResponse, Polling Race, No Tag Size Cap
5159 " ⚖️ Critique Phase — srt Feature PASS: word_timestamps CPU Overhead, MIME Type Non-Standard, JobResponse Collision Risk
5160 11:06a ⚖️ Workflow wf_d002df32 Complete — 3 Features All PASS/WARN, Critical JobResponse Sequencing Order Established
S1379 VPS Docker deployment architecture decision — Option A (lift-and-shift) vs Option B (production-grade multi-container) (May 31, 12:54 PM)
5216 7:29p ⚖️ VPS Deployment Strategy: Docker Container
S1383 Architecture VPS Cloudflare Tunnel — suppression de nginx, passage à un single-container FastAPI + React statique (May 31, 7:29 PM)
5235 7:46p 🔵 VPS entièrement derrière Cloudflare — nginx potentiellement redondant
S1389 TikTok Analyzer VPS deployment architecture — corrected infra conventions after consulting VPS skill, planning production Dockerfile and code changes before GitHub push (May 31, 7:46 PM)
5238 8:03p 🔵 Project Has Existing Docker Compose Setup with Multiple Images
S1390 Clarifying the real Docker Compose architecture on the VPS — centralized vs. per-project (May 31, 9:54 PM)
### Jun 1, 2026
5251 6:45a 🔵 Correction: Docker Compose architecture is centralized, not per-project
S1391 Architectural decision: centralized vs. per-project Docker Compose for deploying tiktok-analyzer on VPS (Jun 1, 6:45 AM)
5255 6:50a 🟣 Dockerfile.prod created for TikTok Analyzer — multi-stage build baking React into Python container
5256 " 🔵 backend/main.py structure: FastAPI app on line 20, ends with /health endpoint, no StaticFiles mount yet
5257 " 🟣 FastAPI backend now serves React build in production via conditional StaticFiles mount
5258 " ✅ Frontend API base URL defaults to empty string in production (same-origin), not localhost:8000
5259 " ✅ JobHistory.jsx API base URL fallback updated to empty string for same-origin production
5260 6:51a 🟣 docker-compose.prod.yml created — per-project compose joining shared docker_app-network
5261 " 🟣 .env.prod.example created — documents all production environment variables and reveals prod domain
5262 " 🔵 .gitignore does not yet ignore .env.prod — only ignores .env and .env.txt
5263 " ✅ .gitignore updated: adds .env.prod, hf_cache/, and dev script patterns
5264 6:52a 🔵 Dev backend confirmed healthy after StaticFiles addition — /app/static absent, mount is no-op as designed
S1393 VPS production deployment setup for TikTok Analyzer — full runbook delivered, all prod files created (Jun 1, 6:52 AM)
**Investigated**: - Dev backend container (tiktokanalyzer-backend-1) verified healthy after StaticFiles conditional addition
    - Existing .gitignore checked before updating
    - backend/main.py structure inspected to find correct insertion point for StaticFiles mount
    - VPS Docker architecture clarified: central compose for infra, per-project composes for apps joining docker_app-network

**Learned**: - Production domain: https://tiktok-analyzer.hen8n.com
    - VPS infra compose lives at /home/projects/docker/docker-compose.yml (Cloudflare Tunnel, n8n, MinIO, Portainer, etc.)
    - Cloudflare Tunnel config lives at /home/projects/docker/cloudflare-config/config.yml — new service added as ingress rule before catch-all
    - Whisper medium model (~1.5 GB) downloads at first transcription request, not at build time — mitigated by tiktok_hf_cache named volume
    - SCRIPT_INBOX_DIR left empty in prod (no Obsidian on VPS) — scripts accessible via GET /jobs/{id}/script.txt instead
    - StaticFiles conditional mount confirmed no-op in dev (/app/static does not exist in dev container)
    - StaticFiles MUST be mounted after all API routes — it's a catch-all that shadows anything declared after it
    - Frontend API constant was duplicated in App.jsx AND JobHistory.jsx — both updated
    - Files to clean up before push: _test_whisper.py, _backfill_tags_description.py, frontend/src/components/TranscriptionPrompt.jsx

**Completed**: - Dockerfile.prod created: multi-stage Node+Python build, React dist baked into /app/static
    - backend/main.py updated: conditional StaticFiles mount at "/" after all API routes
    - frontend/src/App.jsx updated: API fallback changed from 'http://localhost:8000' to ''
    - frontend/src/components/JobHistory.jsx updated: same API fallback fix
    - docker-compose.prod.yml created: per-project compose, no host ports, joins docker_app-network, two named volumes
    - .env.prod.example created: full template with all required env vars documented
    - .gitignore updated: added .env.prod, hf_cache/, _test_*.py, _backfill_*.py
    - Full VPS deployment runbook delivered (git push → clone → .env.prod → docker build → cloudflared ingress → DNS → verify)

**Next Steps**: Decision pending on whether to create a deploy.sh script (git pull + rebuild + restart in one command) before pushing to GitHub and executing the deployment on the VPS.


Access 214k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>