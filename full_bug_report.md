# 🐛 Full Bug & Issues Report — Quote-Pro

> Every issue found across the entire codebase. Nothing is fixed — just documented.

---

## 🔴 CRITICAL (Will Break / Security Risk)

### 1. `.env` has REAL API keys & credentials committed to Git
**File:** `.env`
- Lines 10, 24, 25, 29–30: Live Groq API key, Supabase URL+key, Gmail app password, and Flask secret key are all hard-coded and committed.
- This is a **severe security leak** — anyone with repo access can hit your DB, send emails, and use your AI quota.

---

### 2. Path Traversal vulnerability in `/download/file/<path:filename>`
**File:** `app.py` line 278
```python
filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
```
- Using `<path:filename>` allows `../../../etc/passwd` style traversal.
- There is **no check** that the resolved path is still inside `OUTPUT_FOLDER`.
- An attacker can download any file the server process can read.

---

### 3. SHA-256 password hashing — no salt
**File:** `auth_service.py` lines 28–30
```python
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.strip().encode()).hexdigest()
```
- Plain SHA-256 with no salt is trivially reversible with rainbow tables.
- Should use `bcrypt`, `argon2`, or at minimum `hashlib.pbkdf2_hmac`.

---

### 4. `save_history` silently swallows all exceptions
**File:** `auth_service.py` lines 106–157
```python
except Exception:
    pass
```
- The outer `except Exception: pass` on line 156 silently drops ALL errors, including DB connection failures, network issues, etc.
- Users' chat history can fail to save with zero feedback — they won't even know.

---

### 5. `list_all_users()` has no error handling
**File:** `auth_service.py` lines 280–288
```python
def list_all_users() -> list:
    result = supabase.table("users").select(...).execute()
    return result.data
```
- No `try/except`. If Supabase is unreachable, this will raise an unhandled exception that crashes the `/admin/users` endpoint with a 500 error and a full traceback.
- Same issue in `admin_delete_session()` line 294–296 and `delete_history_file()` line 263–266.

---

### 6. `_send_quotation_as_email` return type annotation is wrong
**File:** `app.py` line 288
```python
def _send_quotation_as_email(format: str) -> tuple:
```
- It actually returns a Flask `Response` object from `jsonify()`, not a Python `tuple`. The annotation is misleading and will confuse type checkers.

---

### 7. OCR dependencies not in `requirements.txt`
**File:** `requirements.txt` + `modules/ocr_handler.py`
- `ocr_handler.py` imports: `easyocr`, `cv2` (opencv-python), `pdf2image`, `Pillow`, `numpy`
- **None of these are listed in `requirements.txt`**.
- If someone deploys the app (Render, etc.), OCR imports will fail silently (caught by try/except), but image/scanned PDF uploads will return "OCR not enabled" errors.

---

### 8. Template path is relative, not absolute — will break in production
**File:** `modules/document_generator.py` lines 122, 160
```python
template_path = os.path.join('templates', 'type1', 'type1_template.html')
```
- This path is **relative to the current working directory**, not the file's location.
- When running via Gunicorn from a different working directory (common on Render), this raises `FileNotFoundError` and PDF generation breaks completely.
- Should use `os path.join(os.path.dirname(__file__), '..', 'templates', ...)`.

---

## 🟠 BUGS (Wrong Behavior)

### 9. `GROQ_MODEL` in `config.py` is never actually used
**File:** `config.py` line 33
```python
GROQ_MODEL = "mixtral-8x7b-32768"
```
- `LLMHandler` hardcodes `"llama-3.3-70b-versatile"` on its own (line 22 of `llm_handler.py`).
- This `GROQ_MODEL` config variable is defined but **never consumed anywhere**.

---

### 10. `get_llm_handler()` is defined but never called
**File:** `app.py` lines 52–56
```python
def get_llm_handler():
    if not hasattr(_local, 'llm_handler'):
        _local.llm_handler = LLMHandler()
    return _local.llm_handler
```
- This thread-local helper is defined, but every route that needs an LLM handler **creates a new `LLMHandler()` directly** (lines 215, 441). The helper function is dead code.

---

### 11. `extract_requirements_text()` in `chatbot_service.py` is never called from Flask routes
**File:** `chatbot_service.py` lines 118–131
- `extract_requirements_text()` is defined but never imported or called by `app.py`.
- `expand_to_requirements()` is used instead. The function is dead code.

---

### 12. Admin page: delete session doesn't update the chat count badge
**File:** `templates/admin.html` lines 584–589
```javascript
await fetch(`/admin/user/${u.key}/chat/${s.session_id}/delete`, { method: 'POST' });
row.remove();
```
- When a session is deleted, the row is removed from the sidebar, but the **chat count badge** on the user card in the overview grid and sidebar still shows the old (stale) count.
- There is no re-fetch or decrement of the counter.

---

### 13. Admin page: overview grid is shown even when no users are loaded yet
**File:** `templates/admin.html` line 519
```javascript
gridEl.style.display = 'grid';
```
- On first load `loadUsers()` correctly hides the placeholder and shows the grid — but if the fetch fails (network error), `data.success` is false and the function returns early on line 471 WITHOUT hiding the placeholder properly (it leaves the spinner in `userList`).

---

### 14. Admin: `headerDot` visibility inconsistency
**File:** `templates/admin.html` lines 532, 556
- When selecting a user the dot is hidden: `headerDot.style.display = 'none'`
- When clicking "All Users" back button, it's restored: `headerDot.style.display = 'block'`
- But `block` on a `span.dot-green` is wrong — it should be kept as `inline-block` (or rely on the CSS class). This makes the dot take up full width instead of being a small circle.

---

### 15. `download_file` route sends wrong `download_name`
**File:** `app.py` line 281
```python
return send_file(filepath, as_attachment=True, download_name=filename)
```
- `filename` here contains the full relative path (e.g., `subdir/file.pdf` if path traversal happens), not just the basename.
- Should be `download_name=os.path.basename(filename)`.

---

### 16. `_create_word_type2` has a typo in bank details label
**File:** `modules/document_generator.py` line 343
```python
f"Account Nam: {data.get('account_name', 'MJ Services')}",
```
- `"Account Nam:"` is missing the final `e` — should be `"Account Name:"`.

---

### 17. `asyncio.run()` in `voice_service.py` will fail under Gunicorn with uvloop/gevent
**File:** `voice_service.py` line 65
```python
return asyncio.run(_synthesize_async(text, voice))
```
- `asyncio.run()` creates a new event loop. In some Gunicorn worker configurations (gevent, uvloop, eventlet), there's already a running loop and this raises `RuntimeError: This event loop is already running`.
- The comment says "Flask runs requests in threads without existing event loops" — true for sync workers, but risky for async workers.

---

### 18. `handleFile()` in `main.js` only validates MIME type, not extension
**File:** `static/js/main.js` lines 226–230
```javascript
const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument...', 'application/msword'];
if (!validTypes.includes(file.type)) { ... }
```
- The config allows `.xlsx`, `.xls`, `.png`, `.jpg`, `.jpeg`, `.tiff` but the frontend completely blocks them.
- Users can only upload Word/PDF through the UI even though the backend supports Excel/image files.

---

### 19. `showPreview()` in `main.js` uses inline styles with hardcoded hex color
**File:** `static/js/main.js` line 339
```javascript
<h4 style="color: #667eea; ...">
```
- This hardcoded color `#667eea` has **no relation to the design system** or CSS variables. In dark mode it won't match the rest of the theme.

---

### 20. Download buttons reset to emoji text, losing Lucide icons
**File:** `static/js/main.js` lines 407–410
```javascript
downloadPdfBtn.innerHTML = '📄 Download PDF';
downloadWordBtn.innerHTML = '📝 Download Word';
```
- After download, buttons are reset to emoji strings, losing the original `<i data-lucide="...">` icon markup.
- Lucide icons are never re-created after this. Buttons look different after the first download.

---

### 21. `chat.html` not read yet, but from the `/chat/generate` route logic — `summary_ready` flag is never used in the UI to auto-trigger quotation
**File:** `app.py` line 402
```python
'summary_ready': result['summary_ready'],
```
- `summary_ready` is returned to the frontend in every `/chat/message` response. Whether the chat.html frontend actually *uses* this to auto-show a "Generate Quotation" button or popup needs to be verified — but the detection phrase `"Here's everything I've gathered so far:"` (in `chatbot_service.py` line 100) is fragile and can be broken by any LLM response variation.

---

## 🟡 DESIGN / LOGIC ISSUES

### 22. `register` route allows already-logged-in users to re-register via POST
**File:** `app.py` line 119–120
```python
if 'user' in session:
    return redirect(url_for('index'))
```
- GET is blocked correctly, but if someone sends a direct POST to `/register` while logged in... actually this is handled. ✅ But notice — the login button text says just "Sign" (line 271 of `auth.html`):
```html
<button type="submit" class="auth-btn">Sign<i data-lucide="arrow-right" ...></i></button>
```
- **"Sign" with an arrow icon** — the text is incomplete. Should be "Sign In".

---

### 23. `auth.html` subtitle element is empty
**File:** `templates/auth.html` line 232
```html
<div class="subtitle"></div>
```
- The subtitle `div` exists but is completely empty. Leaves dead whitespace in the layout.

---

### 24. `SESSION_COOKIE_SECURE` is NOT set
**File:** `config.py`
- `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = 'Lax'` are set, but **`SESSION_COOKIE_SECURE = True` is missing**.
- In production (HTTPS), the session cookie will be sent over HTTP too, enabling cookie theft via network sniffing.

---

### 25. `PERMANENT_SESSION_LIFETIME` is set but `session.permanent` is never set to `True`
**File:** `config.py` line 24, `app.py`
```python
PERMANENT_SESSION_LIFETIME = 60 * 60 * 8   # 8 hours
```
- This setting only applies to **permanent sessions**. Since no route calls `session.permanent = True`, the session expires when the browser closes instead (browser-session cookie).
- The 8-hour expiry is **completely ignored**.

---

### 26. Uploaded files are never cleaned up / deleted
**File:** `app.py` lines 175–180
- Files are saved to `uploads/` folder on every upload.
- There is **no cleanup mechanism** — files accumulate indefinitely. On a hosted server (Render free tier), the ephemeral disk fills up and the app breaks.

---

### 27. Generated output files are never cleaned up
**File:** `modules/document_generator.py` + `app.py`
- Every PDF/Word download creates a new file in `outputs/`.
- Same issue as above — no TTL or cleanup. The folder grows forever.

---

### 28. `config.py` `UPLOAD_FOLDER` and `OUTPUT_FOLDER` are relative paths with no base
**File:** `config.py` lines 36–37
```python
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
```
- Relative to whatever the CWD is at runtime. On Render this is usually the repo root, which works — but it's fragile. Should use `os.path.join(os.path.dirname(__file__), 'uploads')`.

---

### 29. `company_key()` can create collisions between different company names
**File:** `auth_service.py` lines 33–35
```python
def company_key(company: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", company.strip().lower())
```
- `"Acme Corp"` → `"acme_corp"`, `"Acme  Corp"` → `"acme__corp"` (double underscore), `"Acme-Corp"` → `"acme_corp"`.
- `"Acme Corp"` and `"Acme-Corp"` produce the **same key** → login collision. One user's login leaks into another company's account lookup.

---

### 30. `list_histories()` counts the anchor row in message count
**File:** `auth_service.py` line 181
```python
sessions[sid]["messages"].append(1)
```
- Every row from Supabase appends a `1` to the messages list, including the `seq=-1` anchor row (which contains the JSON blob, not a real message).
- So every session's `message_count` shown in admin is inflated by 1.

---

### 31. `admin_users` route counts anchor rows in `chat_count`
**File:** `app.py` lines 541–542
```python
histories = list_histories(u['key'])
u['chat_count'] = len(histories)
```
- `list_histories` returns one item per unique `session_id` — that part is fine.
- But the count in the overview card `ov-stat-val` shows sessions not messages, while the badge says "X chats". These are session counts, not message counts, which is confusing.

---

### 32. `MAX_TOKENS = 256` in `chatbot/config.py` is extremely low for a chatbot
**File:** `chatbot/config.py` line 19
```python
MAX_TOKENS = 256
```
- 256 tokens allows roughly 3–4 sentences. The CRM system prompt requires multi-question conversations plus a full summary section.
- The AI will consistently truncate mid-response, producing incomplete answers.

---

### 33. `expand_to_requirements` fallback silently returns raw transcript on API failure
**File:** `chatbot_service.py` lines 164–166
```python
except Exception:
    return extract_requirements_text(history)
```
- No logging of the failure. If the expansion step fails, the raw chatbot conversation is passed directly to `generate_quotation()`, which will produce a poor/garbled quotation. No error is surfaced to the user.

---

### 34. `gunicorn.conf.py` exists but its contents haven't been audited
**File:** `gunicorn.conf.py` (not read — worth checking worker/thread counts for the claimed 30 concurrent users)

---

### 35. `render.yaml` not read — deployment config unchecked
**File:** `render.yaml` — not audited for environment variable injection or health-check path correctness.

---

## 🟢 MINOR / COSMETIC

### 36. Admin page: no "mobile menu open" button visible
**File:** `templates/admin.html`
- On mobile, the sidebar is hidden (`transform: translateX(-100%)`), but there is **no hamburger/menu button** added anywhere on mobile to trigger `sidebar.classList.add('open')`. The sidebar becomes completely inaccessible on small screens.

### 37. `auth.html` login button text is "Sign" not "Sign In"
**File:** `templates/auth.html` line 271
```html
Sign<i data-lucide="arrow-right" ...></i>
```
- Just says "Sign" — missing the "In" text.

### 38. Admin tooltip CSS classes (`tooltip-name`, `tooltip-company`, etc.) are not defined
**File:** `templates/admin.html` lines 393–411
- `.tooltip-name`, `.tooltip-company`, `.tooltip-row`, `.tooltip-icon`, `.tooltip-actions`, `.tooltip-logout` are used in admin's `admin-tooltip` div but these styles are **only defined in** `static/css/style.css` (assumed). If those rules are in `style.css` only for the `index.html` user-pill tooltip, they may not apply properly because the admin page overrides the entire body layout.

### 39. `main.js` has multiple `console.log` debug statements left in
**File:** `static/js/main.js` lines 279–313
```javascript
console.log('Generate button clicked');
console.log('Requirements:', requirements);
// etc.
```
- 6 `console.log` statements are left in production code, including printing raw requirements text and API response data.

### 40. `load_history_file` will raise `KeyError` if Supabase returns rows missing `seq`
**File:** `auth_service.py` line 204
```python
.order("seq", desc=False)
```
- If the `seq` column doesn't exist in Supabase, `except Exception` falls back to `created_at` ordering (line 208–216). But the fallback result still goes through `_sort_key()` which calls `r.get("seq")` — this returns `None` safely because it uses `.get()`. ✅ Actually this part is okay.

### 41. `ocr_handler.py` imports `easyocr`, `cv2`, `pdf2image` at module level
**File:** `modules/ocr_handler.py` lines 7–12
- These heavy imports run at module load time. Even with the `try/except ImportError` wrapper in `document_parser.py`, if these packages ARE installed, `EasyOCR` loads its neural models into memory on startup — adding several seconds to server cold-start and significant RAM usage.

### 42. `voice_service.py` truncates TTS input to 3000 chars without user notification
**File:** `voice_service.py` line 46
```python
clean = clean[:3000]
```
- Silently truncates long AI responses. User hears partial audio with no indication the message was cut.

---

## Summary Table

| Severity | Count | Category |
|----------|-------|----------|
| 🔴 Critical | 8 | Security, data loss, deployment failures |
| 🟠 Bug | 14 | Wrong behavior, broken UI, dead code |
| 🟡 Logic | 12 | Design flaws, bad defaults, UX gaps |
| 🟢 Minor | 8 | Cosmetic, debug code, typos |
| **Total** | **42** | |
