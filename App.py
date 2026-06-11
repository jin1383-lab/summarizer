import streamlit as st
import re
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

# 페이지 설정
st.set_page_config(page_title="유튜브 스크립트 요약기 (Gemini)", page_icon="📹", layout="centered")

st.title("📹 유튜브 스크립트 번역 및 요약기")
st.caption("Gemini AI를 활용해 유튜브 영상의 자막을 추출하고 한국어로 번역 및 요약합니다.")

# 1. 유튜브 URL에서 Video ID를 추출하는 함수
def extract_video_id(url):
    # 다양한 유튜브 URL 형태 대응 (일반, 단축, Shorts 등)
    pattern = r'(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

# 2. 유튜브 자막 추출 함수
def get_youtube_transcript(video_id):
    try:
        # 우선 한국어('ko') 자막 시도, 없으면 영어('en') 자막 시도
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        # 타임스탬프를 제외하고 텍스트만 병합
        full_text = " ".join([item['text'] for item in transcript_list])
        return full_text
    except Exception as e:
        st.error("자막을 가져오지 못했습니다. 자막(자동생성 포함)이 활성화되어 있는지 확인해 주세요.")
        return None

# 3. Gemini API 환경 설정 및 요약 요청 함수
def summarize_with_gemini(text):
    try:
        # Streamlit Secrets 또는 로컬 secrets.toml에서 API 키 로드
        api_key = st.secrets["GEMINI_API_KEY"]
        
        # 최신 google-genai 클라이언트 초기화
        client = genai.Client(api_key=api_key)
        
        # AI에게 줄 프롬프트 작성 (번역 및 요약 지시)
        prompt = f"""
        당신은 전문 콘텐츠 요약가이자 번역가입니다.
        아래 제공된 유튜브 영상의 스크립트(대본)를 바탕으로 다음 작업을 수행해 주세요:
        
        1. 전체 내용을 명확하고 자연스러운 한국어로 번역해 주세요.
        2. 영상의 핵심 내용을 3~5개의 핵심 포인트를 두어 깔끔하게 요약해 주세요.
        3. 전체적인 주제나 결론을 한 줄로 요약해 주세요.
        
        [유튜브 스크립트 본문]
        {text}
        """
        
        # 2025-2026년 표준 가성비/고성능 모델인 gemini-2.5-flash 활용
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except KeyError:
        st.error("API 키 설정이 누락되었습니다. `.streamlit/secrets.toml` 파일이나 Streamlit Cloud의 Secrets 설정을 확인하세요.")
        return None
    except Exception as e:
        st.error(f"Gemini API 호출 중 오류가 발생했습니다: {e}")
        return None

# --- UI 컴포넌트 구성 ---

# 사용자 URL 입력
video_url = st.text_input("유튜브 영상 링크를 입력하세요:", placeholder="https://www.youtube.com/watch?v=...")

if video_url:
    video_id = extract_video_id(video_url)
    
    if not video_id:
        st.warning("유효한 유튜브 주소가 아닙니다. URL을 다시 확인해 주세요.")
    else:
        # 유튜브 섬네일 미리보기 (선택 사항)
        st.image(f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg", width=360)
        
        # 실행 버튼
        if st.button("스크립트 추출 및 요약 시작"):
            # Step 1: 자막 가져오기
            with st.spinner("유튜브 서버에서 자막을 추출하는 중..."):
                transcript_text = get_youtube_transcript(video_id)
            
            # Step 2: 자막이 정상적으로 추출되었으면 Gemini로 요약
            if transcript_text:
                with st.spinner("Gemini AI가 번역 및 요약을 진행 중입니다..."):
                    summary_result = summarize_with_gemini(transcript_text)
                
                if summary_result:
                    st.success("분석 완료!")
                    
                    # 탭을 나누어 결과 보여주기
                    tab1, tab2 = st.tabs(["📌 AI 요약 및 번역 결과", "📑 원본 자막 텍스트"])
                    
                    with tab1:
                        st.markdown(summary_result)
                        
                    with tab2:
                        st.text_area("추출된 전체 자막", transcript_text, height=300)
