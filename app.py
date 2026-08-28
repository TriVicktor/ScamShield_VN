"""
ScamShield VN — Trợ lý AI Phòng Chống Lừa Đảo Trực Tuyến
Hackathon: AI Riser Vietnam 2026
Stack: Streamlit + Google Gemini (text & vision) + Google Maps embed
"""

import json
import os
import urllib.parse
from datetime import datetime

import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
from PIL import Image

# ──────────────────────────────────────────────────────────────────────────
# CẤU HÌNH TRANG
# ──────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ScamShield VN  | Trợ lý AI Phòng Chống Lừa Đảo",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MODEL_NAME = "gemini-3.5-flash"

SYSTEM_PROMPT = """
# OUTPUT CONTRACT

Return ONLY valid JSON.

Do not use Markdown.

Do not use code fences.

Do not add explanations outside the JSON object.

## LANGUAGE REQUIREMENT

All human-readable text values inside the JSON MUST be written entirely in Vietnamese.

This includes:

* summary
* anomaly_points.quote
* anomaly_points.analysis
* anomaly_points.category
* anomaly_points.evidence_status
* psychological_tactics.tactic
* psychological_tactics.evidence
* psychological_tactics.confidence
* recommended_actions
* organization_to_verify

JSON keys MUST remain exactly as specified below and MUST NOT be translated.

Technical identifiers and enum values defined by this schema are exceptions and MUST remain exactly as specified.

Do NOT mix Vietnamese and English inside human-readable text fields unless the English text is an exact quotation from the user's input.

When quoting the user's message, preserve the original wording exactly. Therefore, anomaly_points.quote MAY contain English text if and only if that English text actually appears in the user's input.

---

## REQUIRED JSON STRUCTURE

The output MUST contain exactly these six top-level fields:

{
"risk_score": integer,
"risk_level": "SAFE | LOW | MEDIUM | HIGH | CRITICAL",
"summary": string,
"organization_to_verify": string | null,
"anomaly_points": [
{
"quote": string,
"analysis": string,
"category": string,
"weight": integer,
"evidence_status": "verified_from_input | strong_inference | unverified"
}
],
"psychological_tactics": [
{
"tactic": string,
"evidence": string,
"confidence": "high | medium | low"
}
],
"recommended_actions": [
string
]
}

---

## FIELD RULES

### risk_score

Must be an integer from 0 to 100.

Do not return a decimal.

Example:

"risk_score": 87

NOT:

"risk_score": 87.5

---

### risk_level

Must be exactly one of:

* SAFE
* LOW
* MEDIUM
* HIGH
* CRITICAL

Use the previously defined numerical thresholds and Critical-Risk Override rules.

---

### summary

Provide ONE concise Vietnamese sentence summarizing the overall risk.

The sentence must:

* be understandable to a normal Vietnamese user;
* state the overall risk situation;
* avoid unsupported claims;
* not introduce evidence that does not exist in the input.

Example:

"Tin nhắn có nhiều dấu hiệu lừa đảo và yêu cầu người nhận cài ứng dụng không rõ nguồn gốc."

Do NOT write a generic statement such as:

"Có vẻ nguy hiểm."

---

### organization_to_verify

Purpose:

Extract the name of the organization, government agency, bank, company, platform, or other institution that the suspicious message claims to represent or impersonate.

Return:

* the exact organization name found in the input, if clearly identifiable;
* otherwise `null`.

IMPORTANT:

Do NOT infer or invent an organization name.

If the message says:

"Ngân hàng ABC"

return:

"Ngân hàng ABC"

If the message contains:

"cơ quan công an"

but does not identify a specific police organization:

return:

null

If multiple organizations are mentioned, select the organization that the sender most directly claims to represent or impersonate.

Do NOT return:

* a person's name;
* a phone number;
* an email address;
* a URL;
* an account number;
* an address;
* an organization merely mentioned incidentally.

If it is unclear which organization is being impersonated:

return `null`.

---

### anomaly_points

Each object represents one distinct, evidence-based anomaly.

"quote":

Must contain an exact quotation from the user-provided text whenever possible.

For image input, quote only text that is clearly readable.

Never fabricate missing or unreadable text.

"analysis":

Explain briefly in Vietnamese why the quoted evidence increases or decreases the assessed risk.

"category":

Use a concise Vietnamese category name such as:

* "Mạo danh cơ quan"
* "Yêu cầu chuyển tiền"
* "Yêu cầu cung cấp OTP"
* "Liên kết đáng ngờ"
* "Cài đặt ứng dụng không rõ nguồn gốc"
* "Tạo cảm giác khẩn cấp"
* "Lừa đảo việc nhẹ lương cao"

"weight":

Must be the actual score contribution assigned to this anomaly.

If there is no evidence-based score contribution, do not create a positive-weight anomaly.

"evidence_status":

This is a technical enum and MUST remain exactly:

* "verified_from_input"
* "strong_inference"
* "unverified"

---

### psychological_tactics

All human-readable descriptions MUST be written in Vietnamese.

"tactic" should identify the manipulation technique.

Examples:

* "Tạo cảm giác khẩn cấp"
* "Đe dọa hậu quả pháp lý"
* "Mạo danh người có thẩm quyền"
* "Đánh vào lòng tham tài chính"
* "Cô lập nạn nhân"
* "Tạo cảm giác sợ mất tài khoản"

"evidence" must describe the supporting evidence from the input.

"confidence" is a technical enum and MUST remain exactly:

* "high"
* "medium"
* "low"

Do not identify a psychological tactic without observable supporting evidence.

---

### recommended_actions

Return practical, prioritized actions in Vietnamese.

Actions should be directly relevant to the detected risk.

Examples:

* "Không nhấp vào liên kết trong tin nhắn."
* "Không cài đặt tệp APK được gửi từ nguồn không xác minh."
* "Không cung cấp mã OTP, mật khẩu hoặc mã PIN."
* "Không chuyển tiền theo hướng dẫn trong tin nhắn."
* "Xác minh thông tin thông qua website hoặc số điện thoại chính thức của tổ chức."
* "Nếu đã cung cấp thông tin ngân hàng, hãy liên hệ ngân hàng qua kênh chính thức ngay lập tức."

IMPORTANT:

Never instruct the user to verify through a phone number, URL, QR code, email address, or account number contained in the suspicious message itself.

---

## STRICT VALIDATION BEFORE RESPONSE

Before returning the JSON, verify all of the following:

1. The response is valid JSON.
2. There are exactly six top-level fields.
3. All required fields are present.
4. `risk_score` is an integer from 0 to 100.
5. `risk_level` is one of the allowed enum values.
6. `summary` is exactly one concise Vietnamese sentence.
7. `organization_to_verify` is either a string extracted from the input or `null`.
8. No organization name has been invented.
9. Every positive anomaly weight is supported by observable evidence.
10. Every `quote` exists in the supplied input or is directly readable from the supplied image.
11. Duplicate evidence has not been double-counted.
12. All human-readable generated text is in Vietnamese.
13. Technical JSON keys and enum values remain unchanged.
14. No Markdown or text exists outside the JSON object.

Return ONLY the final JSON object.
"""

# Prompt của ChatGPT trả về risk_level dạng enum kỹ thuật (SAFE|LOW|MEDIUM|HIGH|CRITICAL).
# Map sang nhãn tiếng Việt hiển thị cho người dùng + màu tương ứng.
LEVEL_DISPLAY = {
    "SAFE": {"label": "An toàn", "color": "#22c55e"},
    "LOW": {"label": "Cảnh báo nhẹ", "color": "#eab308"},
    "MEDIUM": {"label": "Trung bình", "color": "#f59e0b"},
    "HIGH": {"label": "Nguy hiểm", "color": "#f97316"},
    "CRITICAL": {"label": "Cực kỳ nguy hiểm", "color": "#ef4444"},
}

EVIDENCE_STATUS_LABEL = {
    "verified_from_input": "Đã xác thực từ nội dung",
    "strong_inference": "Suy luận có cơ sở",
    "unverified": "Chưa xác thực",
}


def weight_badge(weight) -> str:
    """
    Sinh nhãn 'Scam DNA' hiển thị điểm cộng dồn (weight) của một dấu hiệu đáng ngờ,
    kèm chấm màu theo mức độ đóng góp vào risk_score — giúp người dùng thấy rõ
    TẠI SAO AI chấm điểm rủi ro cao (minh bạch hoá cách tính điểm).
    """
    try:
        w = int(weight)
    except (TypeError, ValueError):
        return ""
    if w <= 0:
        return ""
    if w >= 20:
        icon = "🔴"
    elif w >= 10:
        icon = "🟠"
    else:
        icon = "🟡"
    return f"{icon} +{w} điểm"


# ──────────────────────────────────────────────────────────────────────────
# GIAO DIỆN — CSS "Premium / Modern / Trustworthy"
# ──────────────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"]  {
            font-family: 'Be Vietnam Pro', sans-serif;
        }

        /* Ẩn footer/menu mặc định của Streamlit để giao diện gọn hơn */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        .stApp {
            background: radial-gradient(circle at 15% 0%, #101a2c 0%, #0b1120 45%, #070b14 100%);
        }

        /* ---------- HERO ---------- */
        .hero {
            display: flex;
            align-items: center;
            gap: 18px;
            padding: 28px 32px;
            border-radius: 20px;
            margin-bottom: 28px;
            background: linear-gradient(120deg, rgba(59,130,246,0.16), rgba(16,185,129,0.10));
            border: 1px solid rgba(255,255,255,0.08);
        }
        .hero-icon {
            font-size: 46px;
            line-height: 1;
            filter: drop-shadow(0 0 14px rgba(59,130,246,0.55));
        }
        .hero-title {
            font-size: 34px;
            font-weight: 800;
            color: #f8fafc;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .hero-title span {
            background: linear-gradient(90deg, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-sub {
            color: #94a3b8;
            font-size: 15px;
            margin-top: 4px;
        }
        .badge-row { margin-top: 10px; display:flex; gap:8px; flex-wrap: wrap;}
        .badge {
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            color: #cbd5e1;
        }

        /* ---------- CARD ---------- */
        .glass-card {
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 22px 24px;
            box-shadow: 0 8px 28px rgba(0,0,0,0.25);
            height: 100%;
        }
        .glass-card h3 {
            margin-top: 0;
            color: #f1f5f9;
            font-size: 18px;
            font-weight: 700;
        }

        .section-label {
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 6px;
        }

        /* ---------- LIST ITEMS ---------- */
        .flag-item {
            background: rgba(239,68,68,0.08);
            border-left: 3px solid #ef4444;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
            color: #fecaca;
            font-size: 14.5px;
        }
        .tactic-item {
            background: rgba(168,85,247,0.08);
            border-left: 3px solid #a855f7;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
            color: #e9d5ff;
            font-size: 14.5px;
        }
        .action-item {
            background: rgba(34,197,94,0.08);
            border-left: 3px solid #22c55e;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
            color: #bbf7d0;
            font-size: 14.5px;
        }

        .footer-note {
            text-align: center;
            color: #475569;
            font-size: 12.5px;
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.06);
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            border-radius: 12px;
            height: 48px;
            font-weight: 700;
            font-size: 15.5px;
            background: linear-gradient(90deg, #ef4444, #f97316);
            border: none;
            box-shadow: 0 6px 18px rgba(239,68,68,0.35);
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: 12px;
            font-weight: 600;
        }

        /* Nút "Gửi cảnh báo qua Email" (st.link_button) — giữ tông xanh dương để phân biệt
           với nút "Phân tích ngay" màu đỏ/cam */
        div[data-testid="stLinkButton"] a {
            border-radius: 12px !important;
            font-weight: 700 !important;
            background: linear-gradient(90deg, #3b82f6, #2563eb) !important;
            border: none !important;
            color: white !important;
            box-shadow: 0 6px 16px rgba(37,99,235,0.35) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero_section(configured: bool):
    status_badge = (
        '<span class="badge" style="border-color:#22c55e55;color:#86efac;">🟢 API đã sẵn sàng</span>'
        if configured
        else '<span class="badge" style="border-color:#ef444455;color:#fca5a5;">🔴 Chưa cấu hình API</span>'
    )
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-icon">🛡️</div>
            <div>
                <div class="hero-title">Scam<span>Shield</span> VN</div>
                <div class="hero-sub">Trợ lý AI phân tích &amp; cảnh báo lừa đảo trực tuyến cho người Việt</div>
                <div class="badge-row">
                    <span class="badge">⚡ Google Gemini Vision</span>
                    <span class="badge">🗺️ Google Maps</span>
                    <span class="badge">☁️ Cloud Run</span>
                    {status_badge}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_gauge(score: int, level_code: str):
    """Vẽ biểu đồ gauge trực quan cho điểm rủi ro bằng Plotly. level_code là enum kỹ thuật (SAFE..CRITICAL)."""
    color = LEVEL_DISPLAY.get(level_code, {}).get("color", "#3b82f6")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "%", "font": {"size": 40, "color": color}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#475569"},
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(34,197,94,0.15)"},
                    {"range": [30, 60], "color": "rgba(234,179,8,0.15)"},
                    {"range": [60, 85], "color": "rgba(249,115,22,0.15)"},
                    {"range": [85, 100], "color": "rgba(239,68,68,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=230,
        margin=dict(l=20, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def build_mailto_link(data: dict) -> str:
    """Sinh link mailto: chứa nội dung cảnh báo để người dùng gửi cho người thân/cơ quan chức năng."""
    level_code = data.get("risk_level", "N/A")
    level_label = LEVEL_DISPLAY.get(level_code, {}).get("label", level_code)
    subject = f"[CẢNH BÁO LỪA ĐẢO] Mức độ: {level_label} ({data.get('risk_score', 0)}%)"
    lines = [
        f"Kết quả phân tích từ ScamShield VN — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        f"Mức độ rủi ro: {level_label} ({data.get('risk_score', 0)}%)",
        f"Tóm tắt: {data.get('summary', '')}",
    ]
    org = data.get("organization_to_verify")
    if org:
        lines.append(f"Tổ chức bị nghi mạo danh: {org}")
    lines += ["", "Các dấu hiệu đáng ngờ:"]
    for point in data.get("anomaly_points", []):
        quote = point.get("quote", "")
        analysis = point.get("analysis", "")
        lines.append(f'- [{point.get("category", "")}] "{quote}" — {analysis}')
    lines += ["", "Khuyến nghị xử lý:"]
    lines += [f"- {a}" for a in data.get("recommended_actions", [])]
    lines.append("\n(Nội dung được tạo tự động bởi ScamShield VN, chỉ mang tính tham khảo.)")
    body = "\n".join(lines)
    return f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"


# ──────────────────────────────────────────────────────────────────────────
# CẤU HÌNH API KEY
# Thứ tự ưu tiên: biến môi trường (Cloud Run/Secret Manager) > .streamlit/secrets.toml
# (dùng khi test local, không cần gõ lại mỗi lần chạy) > ô nhập tay ở sidebar.
# ──────────────────────────────────────────────────────────────────────────
def get_secret(key_name: str) -> str | None:
    """Đọc key theo thứ tự: biến môi trường -> .streamlit/secrets.toml -> None."""
    val = os.environ.get(key_name)
    if val:
        return val
    try:
        return st.secrets.get(key_name)  # đọc từ .streamlit/secrets.toml nếu file tồn tại
    except Exception:
        return None


inject_css()

api_key = get_secret("GEMINI_API_KEY")

with st.sidebar:
    st.markdown("### ⚙️ Cấu hình")

    if api_key:
        st.success("Đã tìm thấy `GEMINI_API_KEY`.")
    else:
        st.warning("Chưa tìm thấy `GEMINI_API_KEY`.")
        api_key = st.text_input("Nhập Gemini API Key (chỉ dùng để test local):", type="password")
        st.caption(
            "⚠️ Không commit key vào Git. Cách gọn hơn để khỏi phải nhập lại mỗi lần: "
            "điền vào file `.streamlit/secrets.toml`."
        )


hero_section(configured=bool(api_key))

if not api_key:
    st.info("👈 Nhập API Key ở thanh bên để bắt đầu sử dụng ứng dụng (chỉ cần cho môi trường local).")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_PROMPT)


# ──────────────────────────────────────────────────────────────────────────
# HÀM GỌI GEMINI
# ──────────────────────────────────────────────────────────────────────────
def analyze_with_gemini(text: str | None, image: Image.Image | None) -> dict:
    """
    Gửi nội dung (văn bản và/hoặc ảnh) tới Gemini và ép trả JSON.
    - Nếu có ảnh: dùng khả năng Vision của Gemini để đọc trực tiếp nội dung trong ảnh
      (tin nhắn chụp màn hình, email, SMS...).
    - generation_config response_mime_type="application/json" ép model trả JSON thuần.
    """
    prompt_parts = []
    if image is not None:
        prompt_parts.append(image)
    instruction = "Hãy phân tích nội dung sau (văn bản và/hoặc hình ảnh đính kèm) và xác định mức độ rủi ro lừa đảo:"
    if text:
        instruction += f"\n\nVăn bản: {text}"
    prompt_parts.append(instruction)

    response = model.generate_content(
        prompt_parts,
        generation_config={"response_mime_type": "application/json"},
    )
    return json.loads(response.text)


# ──────────────────────────────────────────────────────────────────────────
# KHU VỰC NHẬP LIỆU
# ──────────────────────────────────────────────────────────────────────────
col_input, col_result = st.columns([1, 1], gap="large")

with col_input:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 📥 Nhập nội dung nghi vấn")

    tab_text, tab_image = st.tabs(["✍️ Dán văn bản", "🖼️ Tải ảnh chụp màn hình"])

    with tab_text:
        user_input = st.text_area(
            "Dán tin nhắn, email, lời mời chào công việc hoặc đường link lạ:",
            height=200,
            placeholder="Ví dụ: Lệnh truy nã từ Công an TP.HCM, yêu cầu chuyển 5 triệu vào tài khoản để hủy hồ sơ...",
            label_visibility="collapsed",
        )

    with tab_image:
        uploaded_image = st.file_uploader(
            "Tải ảnh chụp màn hình tin nhắn / email / SMS đáng ngờ (Gemini Vision sẽ tự đọc nội dung ảnh):",
            type=["png", "jpg", "jpeg", "webp"],
            key="scam_image_uploader",
        )
        pil_image = None
        if uploaded_image is not None:
            pil_image = Image.open(uploaded_image)
            # Chuẩn hoá về RGB: ảnh PNG chụp màn hình thường ở chế độ RGBA (có kênh alpha)
            # hoặc palette (P), một số phiên bản Gemini API xử lý không ổn định với các mode này.
            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")
            st.image(pil_image, caption="Ảnh đã tải lên", width="stretch")

    analyze_btn = st.button("🔍 Phân tích ngay với AI", type="primary", width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────
# KHU VỰC KẾT QUẢ
# ──────────────────────────────────────────────────────────────────────────
with col_result:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Kết quả phân tích AI")

    has_text = bool(user_input.strip()) if "user_input" in dir() else False
    has_image = pil_image is not None

    if analyze_btn and not has_text and not has_image:
        st.info("Vui lòng nhập văn bản hoặc tải ảnh cần kiểm tra.")

    elif analyze_btn:
        # Xoá kết quả phân tích cũ NGAY khi bắt đầu lần mới — nếu lần này lỗi, người dùng
        # sẽ thấy rõ thông báo lỗi thay vì bị "kẹt" nhìn nhầm kết quả của lần phân tích trước.
        st.session_state.pop("last_result", None)
        with st.spinner("Gemini đang quét các dấu hiệu thao túng tâm lý và lừa đảo..."):
            try:
                data = analyze_with_gemini(
                    text=user_input if has_text else None,
                    image=pil_image if has_image else None,
                )
                st.session_state["last_result"] = data
            except json.JSONDecodeError:
                st.error(
                    "Gemini trả về nội dung không phải JSON hợp lệ (có thể do ảnh không đọc được rõ nội dung). "
                    "Hãy thử lại với ảnh rõ nét hơn hoặc dán thêm văn bản mô tả."
                )
            except Exception as e:
                st.error(f"Lỗi phân tích: {str(e)}")
                with st.expander("Xem chi tiết lỗi kỹ thuật (để debug)"):
                    st.exception(e)

    if "last_result" in st.session_state:
        data = st.session_state["last_result"]
        score = int(data.get("risk_score", 0))
        level_code = data.get("risk_level", "")
        level_info = LEVEL_DISPLAY.get(level_code, {"label": level_code or "Chưa xác định", "color": "#3b82f6"})
        level_label, color = level_info["label"], level_info["color"]

        render_gauge(score, level_code)

        st.markdown(
            f"""<div style="text-align:center; margin-top:-14px; margin-bottom: 14px;">
                    <span style="background:{color}22; color:{color}; border:1px solid {color}55;
                    padding:6px 16px; border-radius:999px; font-weight:700; font-size:14px;">
                    {level_label}
                    </span>
                </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(f"**Tóm tắt:** {data.get('summary', '')}")

        with st.expander("🚩 Phân tích Dấu hiệu đáng nghi", expanded=True):
            anomaly_points = data.get("anomaly_points", [])
            if not anomaly_points:
                st.caption("Không phát hiện dấu hiệu đáng ngờ cụ thể nào.")
            for point in anomaly_points:
                quote = point.get("quote", "")
                analysis = point.get("analysis", "")
                category = point.get("category", "")
                status_label = EVIDENCE_STATUS_LABEL.get(point.get("evidence_status", ""), "")
                weight_label = weight_badge(point.get("weight"))
                st.markdown(
                    f'<div class="flag-item">'
                    f'<div style="font-size: 12px; color: #fca5a5; margin-bottom: 4px; display:flex; justify-content:space-between;">'
                    f'<span>[{category}]'
                    + (f' <b style="color:#fecaca;">{weight_label}</b>' if weight_label else "")
                    + f'</span>'
                    + (f'<span style="opacity:0.75;">{status_label}</span>' if status_label else "")
                    + f'</div>'
                    f'<b>Trích dẫn:</b> "{quote}"<br>'
                    f'<b>Phân tích:</b> {analysis}'
                    f'</div>', 
                    unsafe_allow_html=True
                )

        with st.expander("🧠 Thủ thuật thao túng tâm lý", expanded=False):
            CONFIDENCE_LABEL = {"high": "Độ tin cậy cao", "medium": "Độ tin cậy trung bình", "low": "Độ tin cậy thấp"}
            tactics = data.get("psychological_tactics", [])
            if not tactics:
                st.caption("Không phát hiện thủ thuật thao túng tâm lý rõ rệt.")
            for tac in tactics:
                tactic = tac.get("tactic", "")
                evidence = tac.get("evidence", "")
                conf_label = CONFIDENCE_LABEL.get(tac.get("confidence", ""), "")
                st.markdown(
                    f'<div class="tactic-item"><b>{tactic}</b>'
                    + (f' <span style="opacity:0.7; font-size:12px;">({conf_label})</span>' if conf_label else "")
                    + f'<br>{evidence}</div>',
                    unsafe_allow_html=True
                )

        with st.expander("💡 Khuyến nghị xử lý", expanded=False):
            actions = data.get("recommended_actions", [])
            if not actions:
                st.caption("Chưa có khuyến nghị cụ thể.")
            for action in actions:
                st.markdown(f'<div class="action-item">{action}</div>', unsafe_allow_html=True)

        # Nút gửi cảnh báo qua email (mailto: — không cần backend gửi mail)
        # Dùng st.link_button thay vì thẻ <a target="_blank"> tự viết: đây là component
        # chuẩn của Streamlit, không mở tab mới bị "kẹt trắng" như link mailto: cũ.
        mailto_link = build_mailto_link(data)
        st.link_button(
            "✉️ Gửi cảnh báo này qua Email",
            url=mailto_link,
            type="primary",
            width="stretch",
        )

        # Developer Mode / Transparency Terminal — cho phép xem nguyên văn JSON Gemini trả về,
        # minh chứng Output Contract ép AI trả dữ liệu có cấu trúc chuẩn xác.
        with st.expander("🛠️ Developer Mode: Xem dữ liệu JSON gốc", expanded=False):
            st.json(data)
    elif not analyze_btn:
        st.markdown(
            """<div style="text-align:center; padding: 50px 10px; color:#64748b;">
                    <div style="font-size:44px;">🕵️</div>
                    <p>Kết quả phân tích sẽ hiển thị tại đây sau khi bạn nhấn<br>
                    <b>"Phân tích ngay với AI"</b>.</p>
                </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────
# TRA CỨU ĐỊA ĐIỂM (Google Maps nhúng miễn phí — không cần API Key)
# ──────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown("### 📍 Tra cứu địa điểm cơ quan/doanh nghiệp")
st.caption(
    "Lừa đảo thường giả danh trụ sở Công an, Ngân hàng, Cơ quan thuế. "
    "Tra cứu vị trí trên Google Maps dưới đây để đối chiếu thông tin:"
)

auto_org = ""
if "last_result" in st.session_state:
    auto_org = st.session_state["last_result"].get("organization_to_verify") or ""

location_query = st.text_input(
    "Tên cơ quan/tổ chức cần xác minh (tự động điền nếu AI phát hiện có tổ chức bị mạo danh):",
    value=auto_org,
    placeholder="Ví dụ: Công an Phường Bến Nghé, Quận 1, TP.HCM",
)

if "last_result" in st.session_state and not auto_org:
    st.caption(
        "ℹ️ Ô này để trống vì tin nhắn không mạo danh một tổ chức cụ thể nào. "
        "Bạn có thể tự gõ địa danh/địa chỉ cần tra cứu bên trên."
    )

# Chỉ vẽ bản đồ khi có nội dung để tra cứu — không phụ thuộc vào auto_org,
# nên vẫn hoạt động khi người dùng tự gõ tay dù AI không tự điền được gì.
if location_query:
    import streamlit.components.v1 as components

    maps_url = f"https://www.google.com/maps?q={urllib.parse.quote(location_query)}&output=embed"
    components.iframe(maps_url, height=350, scrolling=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """<div class="footer-note">
            🛡️ ScamShield VN — AI Riser Vietnam 2026 · Kết quả phân tích chỉ mang tính tham khảo,
            không thay thế cho xác minh chính thức từ cơ quan chức năng.
        </div>""",
    unsafe_allow_html=True,
)