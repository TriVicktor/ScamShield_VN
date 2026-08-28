
FROM python:3.10-slim
 
WORKDIR /app
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
COPY . .
 
# Cloud Run injects PORT; Streamlit needs these to run correctly behind its proxy
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
 
EXPOSE 8080
 
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]