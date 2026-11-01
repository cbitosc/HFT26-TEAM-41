# AI voice interviewer

## Purpose
An optional 10–12 minute audio-only interview after the coding assessment,
tailored to the company and role, that verifies the candidate understands
their own portfolio and their own submission. It never affects the score.

## Recruiter setup
Company name, role title, job description text, focus competencies, on/off
toggle, interviewer name and voice. Role presets: Backend, Web, ML,
Security. Only recruiter-provided text is used about the company.

## Interview plan
One generator-slot call per interview, cached by input hash.

| Block | Questions | Source |
| --- | --- | --- |
| Warm-up | 1 | Fixed |
| Role and company | 2 | Generated once per role, reused for every candidate of that role |
| Portfolio deep-dive | 2 | Candidate's claims |
| Submission walkthrough | 2 | Candidate's diff, hint log, Trail Map; each has expected_facts (changed file, function, key change) |
| Candidate's questions | 1 | Fixed |

At most one follow-up per question. Hard time limit.

## Voice architecture (free apart from Featherless usage)
- **Listening:** browser Web Speech API (SpeechRecognition) with interim
  captions; end of turn after about 1.5 s of silence; push-to-talk button as
  fallback. Chrome/Edge only. Optional backend fallback: faster-whisper
  base.en on CPU behind a feature flag.
- **Thinking:** POST /interviews/{id}/turn {answer_text} →
  {say_text, audio_url, state}. State machine and guardrails run on the backend.
- **Speaking:** backend proxy to Featherless POST /v1/audio/speech (API key
  never in the browser). Discover models via GET /v1/models (TTS class) and
  voices via GET /v1/audio/voices. Start with Kokoro; compare with one other
  model on 3 sentences for naturalness and latency; record the choice in
  docs/PROGRESS.md (Decisions log). Cache audio by hash(model, voice, text).
- **Orb:** our own React component (Three.js or canvas). States: idle,
  listening, thinking, speaking. Size and motion follow live volume from a
  Web Audio AnalyserNode (mic while listening, TTS playback while speaking).
- **Barge-in:** speech detected during playback stops the audio and listens.

## Token budget rules
1. Scripted text needs no LLM call: plan questions, intro, outro, and
   acknowledgements/transitions from a fixed phrase bank.
2. Plain code decides first: answer under 12 words → scripted nudge; all
   expected_facts mentioned → next question; under 90 s left → next question.
3. Otherwise one small LLM call: system prompt ≤150 tokens; user content =
   current question + latest answer truncated to 120 words + expected_facts;
   no conversation history; output JSON {action: "follow_up" | "next",
   text: ≤25 words}; max_tokens 60; temperature 0.
4. Caps: ≤8 questions, ≤1 follow-up each, ≤10 LLM calls, and
   INTERVIEW_TOKEN_BUDGET tokens per interview. Over budget → scripted only.
5. No end-of-interview LLM summary by default.
6. Log tokens per call and the interview total.

Choosing the interviewer model: test 2–3 small instruct models from the
Featherless catalog on 10 sample answers; pick the smallest that returns
valid JSON with sensible decisions at least 9 times out of 10. Record the
choice in the Decisions log.

## Data
interview_plans table; interview_turn events (speaker, text, ts_start,
ts_end, question_id, llm_used, tokens); stored transcript; audio not stored
by default.

## Report (Interview tab)
Transcript; per submission question, a deterministic explanation-consistency
check (expected_facts mentioned, by normalized keyword and fuzzy match,
shown as "x of y facts"); token usage total. Never part of the final score.
Never measures accent, fluency, or voice traits.

## Guardrails
Says it is an AI at the start; never reveals solutions, hidden tests, or
reference code; never asks about protected attributes (age, religion,
family, nationality, health, etc.); politely refuses off-topic requests;
ends on time; consent screen before mic access that discloses browser
speech recognition may send audio to the browser vendor.

## Build prompts
P4.7–P4.12 in docs/BUILD_PROMPTS.md.
