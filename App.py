import streamlit as st
import os
import re
import time
from yt_dlp import YoutubeDL
from google import genai
from google.genai import types

# 페이지 설정
st.set_page_config(page_title="유튜브 멀티모달 요약기", page_icon="🎬", layout="centered")

st.title("🎬 유튜브 멀티모달 영상 요약기")
st.caption("자막이 없어도 OK! Gemini AI가 영상을 직접 보고 들으며 내용을 분석 및 요약합니다.")

# 1. 유튜브 URL에서 Video ID 추출
def extract_video_id(url):
    pattern = r'(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# 2. yt-dlp를 이용해 유튜브 영상 다운로드 함수 (용량을 위해 낮은 화질/오디오 포함으로 다운로드)
def download_youtube_video(url, video_id):
    output_filename = f"{video_id}.mp4"
    
    # 이미 다운로드한 적이 있다면 재사용
    if os.path.exists(output_filename):
        return output_filename
        
    ydl_opts = {
        # 대용량 방지를 위해 가장 낮은 화질의 비디오와 오디오가 결합된 mp4 선택
        'format': 'worst[ext=mp4]/worst',
        'outtmpl': output_filename,
        'quiet': True,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        
    return output_filename

# 3. Gemini 멀티모달 분석 함수
def analyze_video_with_gemini(video_path):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)
        
        # Step A: 구글 서버에 영상 파일 업로드
        st.info("🔄 영상을 구글 AI 서버로 안전하게 업로드하는 중...")
        video_file = client.files.upload(file=video_path)
        
        # Step B: 대용량 영상의 경우 구글 서버에서 처리(Processing)하는 시간이 필요하므로 대기
        st.info("⏳ Gemini가 영상을 분석할 준비를 하고 있습니다 (잠시만 기다려주세요)...")
        while video_file.state.name == "PROCESSING":
            time.sleep(3)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            st.error("구글 서버에서 영상 처리 중 오류가 발생했습니다.")
            return None

        # Step C: 멀티모달 프롬프트 작성 및 요청
        st.info("🧠 Gemini AI가 영상을 시청하며 요약본을 작성 중입니다...")
        prompt = """
        당신은 최고의 영상 콘텐츠 분석가입니다. 제공된 영상을 주의 깊게 보고 들은 뒤 다음 요구사항에 맞춰 한국어로 작성해 주세요.
        
        1. 이 영상의 핵심 주제와 결론을 한 줄로 명확하게 요약해 주세요.
        2. 영상의 흐름에 따라 어떤 내용들이 전개되는지 3~5개의 핵심 포인트로 나누어 상세히 설명해 주세요. (가능하다면 대략적인 시간대나 시각적 특징도 언급해 주세요)
        3. 영상에서 주목할 만한 흥미로운 부분이나 특징이 있다면 적어주세요.
        """
        
        # 영상 분석에 최적화된 대규모 컨텍스트 모델 사용
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )
        
        # 분석 완료 후 구글 서버에 올린 파일은 매너있게 삭제
        try:
            client.files.delete(name=video_file.name)
        except:
            pass
            
        return response.text

    except KeyError:
        st.error("API 키 설정이 누락되었습니다. `.streamlit/secrets.toml`을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")
        return None

# --- UI 레이아웃 ---
video_url = st.text_input("유튜브 영상 링크를 입력하세요 (Shorts 지원):", placeholder="https://www.youtube.com/watch?v=...")

if video_url:
    video_id = extract_video_id(video_url)
    
    if not video_id:
        st.warning("유효한 유튜브 주소가 아닙니다.")
    else:
        st.image(f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg", width=360)
        
        if st.button("🎬 영상 직접 분석 시작"):
            start_time = time.time()
            
            # 1단계: 내 서버(Streamlit 환경)로 유튜브 영상 다운로드
            with st.spinner("유튜브에서 영상을 가져오는 중... (몇 초 정도 소요됩니다)"):
                try:
                    video_path = download_youtube_video(video_url, video_id)
                except Exception as e:
                    st.error(f"유튜브 영상 다운로드 실패: {e}")
                    video_path = None
            
            # 2단계: Gemini에게 전달하여 요약
            if video_path and os.path.exists(video_path):
                summary_result = analyze_video_with_gemini(video_path)
                
                if summary_result:
                    st.success(f"🎉 분석 완료! (총 소요 시간: {int(time.time() - start_time)}초)")
                    st.markdown("---")
                    st.subheader("📌 AI 영상 분석 결과")
                    st.markdown(summary_result)
                    
                    # 로컬 공간 절약을 위해 다운로드했던 mp4 파일 삭제
                    if os.path.exists(video_path):
                        os.remove(video_path)
