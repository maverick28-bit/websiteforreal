# Demo Video Recording Guide (2 to 3 Minutes)

This guide provides the exact script and step-by-step actions to record your 2 to 3 minute demo video for submission.

---

## 🎬 Recording Plan Overview

| Timecode | Section | Visual on Screen | What to Say / Do |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:25** | **Overview & Architecture** | Web UI at `http://localhost:3000` | Introduce the project, stack (React, FastAPI, LiteLLM, SQLite). Point out header badge. |
| **0:25 – 0:55** | **Live Inference & Multi-turn** | Web UI | Ask *"What is the capital of Japan?"* -> show metadata. Ask follow-up *"What is its population?"* -> show context retention. |
| **0:55 – 1:25** | **LiteLLM Response Caching** | Web UI | Click **+ New Chat**, ask *"What is the capital of Japan?"* -> show instant answer, `LLM_CACHE`, null key ID. |
| **1:25 – 2:00** | **Key Failover & Resilience** | Terminal | Send cURL with `X-Simulate-Failure: key_1=429` -> show fallback to `key_2`. Show `*=429` -> clean HTTP 503. |
| **2:00 – 2:30** | **Automated Tests & Wrap-up** | Terminal + UI | Run `pytest tests/test_api.py -v` (24 passed). Highlight GitHub repo & wrap up. |

---

## 📝 Step-by-Step Script

### 1. Introduction (0:00 - 0:25)
* **Screen**: [http://localhost:3000](http://localhost:3000)
* **Action**: Hover over the `✓ 2 keys` badge in the header.
* **Narration**:
  > *"Hello! This is a demo of my Full-Stack AI Chatbot built for the Lyftr AI assignment. It features automatic API key failover across multiple keys, in-memory response caching with LiteLLM, multi-turn conversation memory backed by SQLite, and a React Vite frontend."*

### 2. Live AI Inference & Multi-turn Memory (0:25 - 0:55)
* **Screen**: [http://localhost:3000](http://localhost:3000)
* **Action**:
  1. Type: `What is the capital of Japan?` and send.
  2. Hover over the metadata card: point out `LIVE_INFERENCE`, `gemini-3.5-flash-lite`, `key_1`, token counts.
  3. Type follow-up: `What is its population?` and send.
  4. Point out that the bot remembers "its" refers to Tokyo and Japan.
* **Narration**:
  > *"Let's test live inference. I'll ask 'What is the capital of Japan?'. As you can see, the response comes back from our LLM with metadata showing LIVE_INFERENCE, model name, latency, token usage, and key_1.*
  >
  > *Now for multi-turn context: 'What is its population?'. The chatbot retrieves historical turns from SQLite, correctly answering with Tokyo's and Japan's population."*

### 3. Response Caching (0:55 - 1:25)
* **Screen**: [http://localhost:3000](http://localhost:3000)
* **Action**:
  1. Click **+ New Chat** in the top right.
  2. Type the identical initial query: `What is the capital of Japan?` and send.
  3. Show the instant response (< 80ms) and metadata badge showing `LLM_CACHE` and `key_id: null`.
* **Narration**:
  > *"Next is response caching. I'll click 'New Chat' to start a fresh session and ask the exact same question again.*
  >
  > *Notice the response returns almost instantly—in under 70 milliseconds! The resolution source displays LLM_CACHE, and key_id is null because it was resolved entirely in-memory by LiteLLM without incurring provider API costs."*

### 4. Key Failover & Resilience (1:25 - 2:00)
* **Screen**: Terminal
* **Action**:
  1. Run the simulated failover command:
     ```powershell
     $headers = @{"Content-Type"="application/json"; "X-Simulate-Failure"="key_1=429"}
     $body = @{session_id="demo-fail"; message="Tell me a joke"} | ConvertTo-Json
     Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST -Headers $headers -Body $body | ConvertTo-Json
     ```
  2. Point out `"key_id": "key_2"` and `"fallback_attempts": 1`.
  3. Show all keys failure:
     ```powershell
     $headers2 = @{"Content-Type"="application/json"; "X-Simulate-Failure"="*=429"}
     Invoke-WebRequest -Uri http://localhost:8000/chat -Method POST -Headers $headers2 -Body $body
     ```
  4. Highlight HTTP 503 and explain that failed requests are never saved in conversation history.
* **Narration**:
  > *"For system resilience, we support multiple API keys. When key_1 simulates a 429 rate limit error, the backend catches it and immediately retries with key_2, succeeding with fallback_attempts: 1.*
  >
  > *If all keys fail, the system cleanly returns HTTP 503 Service Unavailable, and ensures the failed query is never written into the database."*

### 5. Automated Tests & Conclusion (2:00 - 2:30)
* **Screen**: Terminal
* **Action**:
  1. Run pytest:
     ```powershell
     python -m pytest tests/test_api.py -v
     ```
  2. Point out all 24 passed tests.
  3. Return to browser UI.
* **Narration**:
  > *"Finally, our comprehensive pytest suite covers API contracts, validation, session isolation, cache hits, and failover mechanics with 24 passing tests.*
  >
  > *The entire application is Docker-ready and pushed to GitHub at github.com/maverick28-bit/websiteforreal. Thank you!"*
