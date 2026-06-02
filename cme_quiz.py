"""
Anesthesia Journal Digest — Interactive CME Quiz Page Builder
==============================================================
Builds a self-contained, mobile-friendly HTML quiz page from the week's CME
questions. The page:
  - shows all questions with selectable options,
  - reveals nothing until the user clicks "Submit Test",
  - on submit, grades the test, shows the score, and reveals the correct answer
    + explanation under each question,
  - offers a "Download Certificate" button that builds a PDF with jsPDF (CDN).

Also builds the docs/cme/index.html listing of recent quizzes.

No server needed — everything runs client-side and is served from GitHub Pages.
"""

import json
import html
from datetime import datetime


def build_quiz_page(questions: list[dict], date_obj: datetime) -> str:
    """Return a complete interactive HTML quiz page for the given questions."""
    pretty_date = date_obj.strftime("%B %d, %Y")
    iso_date = date_obj.strftime("%Y-%m-%d")
    total = len(questions)

    # The questions are embedded as JSON for the client-side grader. We only
    # send what the page needs (correct letter + explanation + source).
    quiz_data = []
    for q in questions:
        quiz_data.append({
            "correct": q.get("correct", ""),
            "rationale": q.get("rationale", ""),
            "source_article": q.get("source_article", ""),
            "source_journal": q.get("source_journal", ""),
            "source_url": q.get("source_url", ""),
        })
    quiz_json = json.dumps(quiz_data)

    # Build the static question markup (no answers exposed in the DOM/text).
    questions_html = ""
    for i, q in enumerate(questions):
        opts_html = ""
        for letter in ("A", "B", "C", "D"):
            text = q.get("options", {}).get(letter, "")
            if not text:
                continue
            opts_html += f"""
        <label class="option" for="q{i}{letter}">
          <input type="radio" id="q{i}{letter}" name="q{i}" value="{letter}">
          <span class="opt-letter">{letter}</span>
          <span class="opt-text">{html.escape(text)}</span>
        </label>"""

        src_bits = []
        if q.get("source_journal"):
            src_bits.append(html.escape(q["source_journal"]))
        if q.get("source_article"):
            src_bits.append(html.escape(q["source_article"]))
        src_label = " — ".join(src_bits)
        src_url = html.escape(q.get("source_url", "") or "#")

        questions_html += f"""
    <section class="question" id="card{i}" data-index="{i}">
      <div class="qnum">Question {i + 1} <span class="of">of {total}</span></div>
      <div class="qtext">{html.escape(q.get("question", ""))}</div>
      <div class="options">{opts_html}
      </div>
      <div class="result" id="result{i}" hidden></div>
    </section>"""

    return _PAGE_TEMPLATE.format(
        pretty_date=pretty_date,
        iso_date=iso_date,
        total=total,
        questions_html=questions_html,
        quiz_json=quiz_json,
    )


def build_quiz_index(quizzes: list[tuple[str, str]]) -> str:
    """Build docs/cme/index.html listing recent quizzes.

    Args:
        quizzes: [(YYYY-MM-DD, filename)] — newest first.
    """
    items = ""
    for iso_date, filename in quizzes:
        try:
            label = datetime.strptime(iso_date, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            label = iso_date
        items += (
            f'      <li><a href="{html.escape(filename)}">'
            f'Weekly CME — {label}</a></li>\n'
        )
    if not items:
        items = '      <li class="empty">No quizzes published yet.</li>\n'

    return _INDEX_TEMPLATE.format(items=items)


# ── Templates ────────────────────────────────────────────────────────────────
# Note: literal CSS/JS braces are doubled so str.format() leaves them intact.

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anesthesia Digest — Weekly CME ({pretty_date})</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
  :root {{ --navy:#1a5276; --blue:#2e86c1; --green:#1e8449; --red:#c0392b;
          --bg:#f4f6f9; --card:#ffffff; --line:#e3e8ee; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:#2c3e50; line-height:1.5; }}
  header {{ background:linear-gradient(135deg,var(--navy),var(--blue)); color:#fff;
           padding:26px 20px; text-align:center; }}
  header h1 {{ margin:0; font-size:21px; font-family:Georgia,serif; }}
  header p {{ margin:6px 0 0; font-size:13px; opacity:.9; }}
  main {{ max-width:760px; margin:0 auto; padding:18px 16px 60px; }}
  .intro {{ background:#eef5fb; border:1px solid #d6e6f5; border-radius:10px;
           padding:14px 16px; font-size:13px; color:#34516b; margin-bottom:18px; }}
  .question {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
             padding:18px 18px 16px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  .qnum {{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
          color:var(--blue); }}
  .qnum .of {{ color:#9bb1c4; font-weight:600; }}
  .qtext {{ font-size:15px; font-weight:600; margin:6px 0 14px; }}
  .option {{ display:flex; align-items:flex-start; gap:10px; padding:11px 12px;
            border:1px solid var(--line); border-radius:9px; margin:8px 0; cursor:pointer;
            transition:background .12s,border-color .12s; }}
  .option:hover {{ background:#f7fafd; }}
  .option input {{ margin-top:3px; flex:none; }}
  .opt-letter {{ font-weight:700; color:var(--navy); flex:none; }}
  .opt-text {{ font-size:14px; }}
  .option.correct {{ border-color:var(--green); background:#eafaf1; }}
  .option.incorrect {{ border-color:var(--red); background:#fdedec; }}
  .result {{ margin-top:12px; padding:12px 14px; border-radius:9px; font-size:13.5px;
            line-height:1.55; }}
  .result.right {{ background:#eafaf1; border:1px solid #abe2c1; }}
  .result.wrong {{ background:#fdedec; border:1px solid #f3b7b1; }}
  .result .verdict {{ font-weight:700; display:block; margin-bottom:4px; }}
  .result .src {{ display:block; margin-top:8px; font-size:12px; color:#5b6b7a; }}
  .result .src a {{ color:var(--blue); }}
  .actions {{ position:sticky; bottom:0; background:linear-gradient(180deg,rgba(244,246,249,0),var(--bg) 30%);
             padding:16px 0 8px; text-align:center; }}
  button {{ font:inherit; border:none; border-radius:24px; padding:13px 26px; font-weight:700;
           font-size:15px; cursor:pointer; }}
  .btn-submit {{ background:var(--blue); color:#fff; }}
  .btn-submit:disabled {{ background:#9bb9d1; cursor:default; }}
  .btn-cert {{ background:var(--green); color:#fff; margin-left:8px; }}
  .scorebar {{ display:none; background:var(--navy); color:#fff; border-radius:12px;
              padding:16px 18px; text-align:center; margin-bottom:18px; }}
  .scorebar .pct {{ font-size:30px; font-weight:800; }}
  .scorebar .detail {{ font-size:13px; opacity:.9; margin-top:2px; }}
  .namebox {{ display:none; margin-top:12px; }}
  .namebox input {{ font:inherit; padding:9px 12px; border-radius:8px; border:1px solid var(--line);
                   width:230px; max-width:80%; }}
  .warn {{ color:var(--red); font-size:13px; margin-top:10px; display:none; }}
  footer {{ text-align:center; font-size:11px; color:#9bb1c4; padding:24px 16px 40px; }}
  footer a {{ color:#9bb1c4; }}
  @media (max-width:520px) {{ .btn-cert {{ margin:10px 0 0; }} .actions button {{ width:100%; }} }}
</style>
</head>
<body>
  <header>
    <h1>&#127891; Anesthesia Digest — Weekly CME</h1>
    <p>{pretty_date} · {total} single-best-answer questions</p>
  </header>
  <main>
    <div class="scorebar" id="scorebar">
      <div class="pct" id="scorePct">0%</div>
      <div class="detail" id="scoreDetail"></div>
      <div class="namebox" id="namebox">
        <input type="text" id="participant" placeholder="Type your name for the certificate">
      </div>
    </div>

    <div class="intro">
      Answer all {total} questions, then press <strong>Submit Test</strong> to see your score
      and the explanations. This is a self-assessment activity suitable for
      <strong>RCPSC Section 3</strong> credits.
    </div>

    <form id="quizForm">{questions_html}
    </form>

    <p class="warn" id="warn">Please answer all questions before submitting.</p>

    <div class="actions">
      <button type="button" class="btn-submit" id="submitBtn">Submit Test</button>
      <button type="button" class="btn-cert" id="certBtn" style="display:none;">Download Certificate</button>
    </div>
  </main>
  <footer>
    Anesthesia Journal Digest · AI-generated self-assessment · Not affiliated with any journal.<br>
    <a href="index.html">&#8592; All weekly quizzes</a>
  </footer>

<script>
  var QUIZ = {quiz_json};
  var QUIZ_DATE = "{pretty_date}";
  var TOTAL = {total};
  var graded = false;
  var lastScore = 0;

  function escapeHtml(s) {{
    return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }}

  document.getElementById("submitBtn").addEventListener("click", function () {{
    // Require every question answered.
    var unanswered = 0;
    for (var i = 0; i < TOTAL; i++) {{
      if (!document.querySelector('input[name="q' + i + '"]:checked')) unanswered++;
    }}
    if (unanswered > 0 && !graded) {{
      document.getElementById("warn").style.display = "block";
      return;
    }}
    document.getElementById("warn").style.display = "none";
    grade();
  }});

  function grade() {{
    var correct = 0;
    for (var i = 0; i < TOTAL; i++) {{
      var chosen = document.querySelector('input[name="q' + i + '"]:checked');
      var ans = QUIZ[i].correct;
      var picked = chosen ? chosen.value : null;
      if (picked === ans) correct++;

      // Colour the options.
      var labels = document.querySelectorAll('#card' + i + ' .option');
      labels.forEach(function (lab) {{
        var val = lab.querySelector("input").value;
        lab.querySelector("input").disabled = true;
        if (val === ans) lab.classList.add("correct");
        else if (chosen && val === picked) lab.classList.add("incorrect");
      }});

      // Reveal the explanation.
      var res = document.getElementById("result" + i);
      var right = picked === ans;
      var srcHtml = "";
      if (QUIZ[i].source_article) {{
        var label = (QUIZ[i].source_journal ? QUIZ[i].source_journal + " — " : "") +
                    QUIZ[i].source_article;
        var url = QUIZ[i].source_url || "#";
        srcHtml = '<span class="src">Source: <a href="' + url +
                  '" target="_blank" rel="noopener">' + escapeHtml(label) + '</a></span>';
      }}
      res.className = "result " + (right ? "right" : "wrong");
      res.innerHTML = '<span class="verdict">' +
        (right ? "&#10003; Correct" : "&#10007; Your answer: " + (picked || "—") +
                 " · Correct answer: " + ans) + '</span>' +
        escapeHtml(QUIZ[i].rationale) + srcHtml;
      res.hidden = false;
    }}

    lastScore = correct;
    graded = true;
    var pct = Math.round((correct / TOTAL) * 100);
    document.getElementById("scorePct").textContent = pct + "%";
    document.getElementById("scoreDetail").textContent =
      correct + " of " + TOTAL + " correct";
    document.getElementById("scorebar").style.display = "block";
    document.getElementById("namebox").style.display = "block";
    document.getElementById("submitBtn").textContent = "Re-check Answers";
    document.getElementById("certBtn").style.display = "inline-block";
    document.getElementById("scorebar").scrollIntoView({{ behavior: "smooth", block: "start" }});
  }}

  document.getElementById("certBtn").addEventListener("click", function () {{
    if (!graded) return;
    var name = (document.getElementById("participant").value || "").trim();
    var jsPDFNS = window.jspdf || {{}};
    var Ctor = jsPDFNS.jsPDF;
    if (!Ctor) {{ alert("Certificate library failed to load. Check your connection and retry."); return; }}
    var doc = new Ctor({{ orientation: "landscape", unit: "pt", format: "letter" }});
    var W = doc.internal.pageSize.getWidth();
    var pct = Math.round((lastScore / TOTAL) * 100);

    // Border
    doc.setDrawColor(26, 82, 118); doc.setLineWidth(3);
    doc.rect(28, 28, W - 56, doc.internal.pageSize.getHeight() - 56);
    doc.setLineWidth(1);
    doc.rect(38, 38, W - 76, doc.internal.pageSize.getHeight() - 76);

    function center(text, y, size, style, color) {{
      doc.setFont("times", style || "normal");
      doc.setFontSize(size);
      doc.setTextColor.apply(doc, color || [44, 62, 80]);
      doc.text(text, W / 2, y, {{ align: "center" }});
    }}

    center("CME Completion Certificate", 110, 30, "bold", [26, 82, 118]);
    center("Anesthesia Journal Digest Weekly CME", 150, 16, "italic");
    center("Date: " + QUIZ_DATE, 200, 13);
    center("This certifies that", 240, 13);
    center(name || "____________________________", 276, 20, "bold");
    center("completed a " + TOTAL + "-question self-assessment", 312, 13);
    center("Score achieved: " + lastScore + " / " + TOTAL + " (" + pct + "%)", 344, 15, "bold", [30, 132, 73]);
    center("Self-assessment activity — suitable for RCPSC Section 3 credits.", 392, 11);
    center("Retain for your records.", 408, 11);

    var fileDate = "{iso_date}";
    doc.save("CME_Certificate_" + fileDate + ".pdf");
  }});
</script>
</body>
</html>"""


_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anesthesia Digest — Weekly CME Quizzes</title>
<style>
  body {{ margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:#f4f6f9; color:#2c3e50; }}
  header {{ background:linear-gradient(135deg,#1a5276,#2e86c1); color:#fff;
           padding:28px 20px; text-align:center; }}
  header h1 {{ margin:0; font-size:22px; font-family:Georgia,serif; }}
  header p {{ margin:6px 0 0; font-size:13px; opacity:.9; }}
  main {{ max-width:640px; margin:0 auto; padding:22px 18px 60px; }}
  ul {{ list-style:none; padding:0; margin:0; }}
  li {{ background:#fff; border:1px solid #e3e8ee; border-radius:10px; margin:10px 0;
       box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  li a {{ display:block; padding:16px 18px; color:#1a5276; text-decoration:none;
         font-weight:600; font-size:15px; }}
  li a:hover {{ background:#f7fafd; }}
  li.empty {{ padding:16px 18px; color:#9bb1c4; font-style:italic; }}
  footer {{ text-align:center; font-size:11px; color:#9bb1c4; padding:24px 16px; }}
  footer a {{ color:#9bb1c4; }}
</style>
</head>
<body>
  <header>
    <h1>&#127891; Weekly CME Quizzes</h1>
    <p>Anesthesia Journal Digest · self-assessment for RCPSC Section 3</p>
  </header>
  <main>
    <ul>
{items}    </ul>
  </main>
  <footer>
    AI-generated self-assessment · Not affiliated with any journal · <a href="../">&#8592; Audio summaries</a>
  </footer>
</body>
</html>"""
