import streamlit as st
import os
import re
import time
from yt_dlp import YoutubeDL
from google import genai

# 페이지 설정
st.set_page_config(page_title="유튜브 멀티모달 요약기", page_icon="🎬", layout="centered")

st.title("🎬 유튜브 멀티모달 영상 요약기")
st.caption("자막이 없어도 OK! Gemini AI가 영상을 직접 보고 들으며 내용을 분석 및 요약합니다.")

# 1. 유튜브 URL에서 Video ID 추출 함수
def extract_video_id(url):
    pattern = r'(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# 2. 403 차단 우회가 반영된 유튜브 영상 다운로드 함수
def download_youtube_video(url, video_id):
    output_filename = f"{video_id}.mp4"
    cookie_filename = "temp_cookies.txt"
    
    # 이미 같은 영상이 다운로드되어 있다면 재사용
    if os.path.exists(output_filename):
        return output_filename
        
    # Streamlit Secrets에 YOUTUBE_COOKIES가 등록되어 있다면 임시 파일로 생성
    if "YOUTUBE_COOKIES" in st.secrets:
        with open(cookie_filename, "w", encoding="utf-8") as f:
            f.write(st.secrets["YOUTUBE_COOKIES"])

    # 403 Forbidden 차단을 막기 위한 최적의 yt-dlp 옵션 설정
    ydl_opts = {
        # 대용량 방지 및 처리 속도를 위해 가장 낮은 화질의 mp4 다운로드
        'format': 'worst[ext=mp4]/worst',
        'outtmpl': output_filename,
        'quiet': True,
        'no_warnings': True,
        # 일반 브라우저에서 접속하는 것처럼 헤더 위장
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        }
    }
    
    # 임시 쿠키 파일이 생성되었다면 옵션에 주입
    if os.path.exists(cookie_filename):
        ydl_opts['cookiefile'] = cookie_filename
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    finally:
        # 보안을 위해 사용이 끝난 임시 쿠키 파일은 즉시 삭제
        if os.path.exists(cookie_filename):
            os.remove(cookie_filename)
            
    return output_filename

# 3. Gemini 멀티모달 분석 함수
def analyze_video_with_gemini(video_path):
    try:
        # Streamlit Secrets에서 Gemini API 키 로드
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
        
        st.info("🔄 영상을 구글 AI 서버로 업로드하는 중...")
        video_file = client.files.upload(file=video_path)
        
        # 구글 서버 내에서 영상 인코딩/처리가 완료될 때까지 대기
        st.info("⏳ Gemini가 영상을 분석할 준비를 하고 있습니다 (잠시만 기다려주세요)...")
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            st.error("구글 서버에서 영상 처리 중 오류가 발생했습니다.")
            return None

        st.info("🧠 Gemini AI가 영상을 시청하며 요약본을 작성 중입니다...")
        prompt = """
        당신은 최고의 영상 콘텐츠 분석가입니다. 제공된 영상을 주의 깊게 보고 들은 뒤 다음 요구사항에 맞춰 한국어로 작성해 주세요.
        
        1. 이 영상의 핵심 주제와 결론을 한 줄로 명확하게 요약해 주세요.
        2. 영상의 흐름에 따라 어떤 내용들이 전개되는지 3~5개의 핵심 포인트로 나누어 상세히 설명해 주세요. (가능하다면 대략적인 시간대나 시각적 특징도 언급해 주세요)
        3. 영상에서 주목할 만한 흥미로운 부분이나 특징이 있다면 적어주세요.
        """
        
        # 멀티모달 영상 요약에 가장 가성비가 좋고 빠른 최신 표준 모델 사용
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )
        
        # 분석 완료 후 구글 AI 서버의 파일 삭제
        try:
            client.files.delete(name=video_file.name)
        except:
            pass
            
        return response.text

    except KeyError:
        st.error("API 키 설정이 누락되었습니다. `.streamlit/secrets.toml` 파일이나 Streamlit Cloud의 Secrets 설정을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")
        return None

# --- UI 레이아웃 구성 ---
video_url = st.text_input("유튜브 영상 링크를 입력하세요 (Shorts 지원):", placeholder="https://www.youtube.com/watch?v=...")

if video_url:
    video_id = extract_video_id(video_url)
    
    if not video_id:
        st.warning("유효한 유튜브 주소가 아닙니다. URL을 다시 확인해 주세요.")
    else:
        # 유튜브 미리보기 섬네일 표시
        st.image(f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg", width=360)
        
        if st.button("🎬 영상 직접 분석 시작"):
            start_time = time.time()
            
            # 1단계: 서버 환경으로 유튜브 영상 다운로드
            with st.spinner("유튜브에서 영상을 가져오는 중... (몇 초 정도 소요됩니다)"):
                try:
                    video_path = download_youtube_video(video_url, video_id)
                except Exception as e:
                    st.error(f"유튜브 영상 다운로드 실패: {e}")
                    video_path = None
            
            # 2단계: Gemini 멀티모달 분석 진행
            if video_path and os.path.exists(video_path):
                summary_result = analyze_video_with_gemini(video_path)
                
                if summary_result:
                    st.success(f"🎉 분석 완료! (총 소요 시간: {int(time.time() - start_time)}초)")
                    st.markdown("---")
                    st.subheader("📌 AI 영상 분석 결과")
                    st.markdown(summary_result)
                    
                    # 용량 관리를 위해 사용한 지역 서버 내 mp4 파일 즉시 삭제
                    if os.path.exists(video_path):
                        os.remove(video_path)
