import streamlit as st
import google.generativeai as genai
import json
import os

# Cấu hình trang
st.set_page_config(
    page_title="ScamShield VN - Trợ lý AI Phòng Chống Lừa Đảo",
    page_icon="🛡️",
    layout="wide"
)

# Lấy API Key từ Environment Variable hoặc UI
api_key = os.environ.get("GEMINI_API_KEY")

st.title("🛡️ ScamShield VN")
st.caption("Ứng dụng AI phân tích & cảnh báo lừa đảo trực tuyến cho người Việt - Powered by Google Gemini & Google Cloud")

if not api_key:
    api_key = st.sidebar.text_input("Nhập Gemini API Key của bạn:", type="password")

if not api_key:
    st.warning("⚠️ Vui lòng cấu hình GEMINI_API_KEY để tiếp tục sử dụng ứng dụng.")
    st.stop()

# Cấu hình Gemini
genai.configure(api_key=api_key)

SYSTEM_PROMPT = """
Bạn là "ScamShield VN" - Chuyên gia AI phân tích an ninh mạng & phòng chống lừa đảo trực tuyến tại Việt Nam.
Bắt buộc trả về kết quả dưới dạng JSON với cấu trúc:
{
  "risk_score": <int 0-100>,
  "risk_level": "<An toàn | Cảnh báo nhẹ | Nguy hiểm | Cực kỳ nguy hiểm>",
  "summary": "<string>",
  "red_flags": ["<string>"],
  "psychological_tactics": ["<string>"],
  "recommended_actions": ["<string>"]
}
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# Giao diện người dùng
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 Nhập nội dung nghi vấn")
    user_input = st.text_area(
        "Dán tin nhắn, email, lời mời chào công việc hoặc đường link lạ vào đây:",
        height=220,
        placeholder="Ví dụ: Lệnh truy nã từ Công an TP.HCM, yêu cầu chuyển 5 triệu vào tài khoản để hủy hồ sơ..."
    )
    analyze_btn = st.button("🔍 Phân tích ngay với AI", type="primary", use_container_width=True)

with col2:
    st.subheader("📊 Kết quả phân tích AI")
    if analyze_btn and user_input.strip():
        with st.spinner("Gemini đang quét các dấu hiệu thao túng tâm lý và lừa đảo..."):
            try:
                response = model.generate_content(
                    f"Hãy phân tích đoạn văn bản sau: {user_input}",
                    generation_config={"response_mime_type": "application/json"}
                )
                data = json.loads(response.text)

                # Hiển thị mức độ rủi ro
                score = data.get("risk_score", 0)
                level = data.get("risk_level", "Chưa xác định")
                
                if score > 80:
                    st.error(f"🚨 Mức độ rủi ro: **{score}% - {level}**")
                elif score > 50:
                    st.warning(f"⚠️ Mức độ rủi ro: **{score}% - {level}**")
                else:
                    st.success(f"✅ Mức độ rủi ro: **{score}% - {level}**")

                st.progress(score / 100)

                # Tóm tắt
                st.write(f"**Tóm tắt:** {data.get('summary', '')}")

                # Dấu hiệu đỏ & Thủ thuật
                st.markdown("### 🚩 Các dấu hiệu đáng nghi:")
                for flag in data.get("red_flags", []):
                    st.markdown(f"- {flag}")

                st.markdown("### 🧠 Thủ thuật thao túng tâm lý:")
                for tactic in data.get("psychological_tactics", []):
                    st.markdown(f"- `{tactic}`")

                # Khuyên dùng
                st.markdown("### 💡 Khuyến nghị xử lý:")
                for action in data.get("recommended_actions", []):
                    st.markdown(f"✅ {action}")

            except Exception as e:
                st.error(f"Lỗi phân tích: {str(e)}")
    elif analyze_btn:
        st.info("Vui lòng nhập nội dung cần kiểm tra.")

# Tính năng tích hợp Google Maps (Giúp cộng thêm điểm Google Tech)
st.divider()
st.subheader("📍 Tra cứu thực địa địa điểm cơ quan/doanh nghiệp")
st.caption("Lừa đảo thường giả danh các trụ sở Công an, Ngân hàng, Cơ quan thuế. Tra cứu vị trí chính thức trên Google Maps dưới đây:")
location_query = st.text_input("Nhập tên cơ quan/địa chỉ cần xác minh (Ví dụ: Công an Phường Bến Nghé District 1):")
if location_query:
    maps_url = f"https://www.google.com/maps?q={location_query.replace(' ', '+')}&output=embed"
    st.components.v1.iframe(maps_url, height=350, scrolling=True)