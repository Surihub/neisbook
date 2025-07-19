# streamlit_app.py
# ────────────────────────────────────────────────────────────────
#  학생부 독서기록 중복·유사 항목 탐지 스트림릿 앱
#  - 업로드 : 나이스 ‘반별 독서활동상황’ 엑셀(.xlsx) 또는 CSV
#  - 출력   : 학생‧번호별 완전 동일·유사 도서 목록
#  - 보너스 : 로컬 data/ 폴더 샘플 파일 다운로드 버튼
# ────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from kiwipiepy import Kiwi
from pathlib import Path
import matplotlib.pyplot as plt
# ───────────────────── 기본 UI ───────────────────── #
st.set_page_config(
    page_title="독서기록 중복 탐지기",
    page_icon="📚",
    layout="centered",
)
st.title("📚 나이스 독서기록 중복 탐지기")
SAMPLE_PATH = Path(__file__).parent / "data" / "samplebook.xlsx"



# 📝 사용 안내 박스 + 다운로드 버튼 포함
with st.container():
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 16px 20px; border-radius: 8px; line-height: 1.4; font-size: 0.94rem;">
    <h4 style="margin-top: 0;">📘 사용 안내</h4>
    • 같은 책을 <b>중복 기재</b>하거나, 오타 등으로 <b>유사하게 중복</b>된 경우를 찾아줍니다.<br>
    • <b>나이스 → 반별 독서활동상황</b> 엑셀(.xlsx) 또는 CSV 파일을 그대로 올려주세요.<br>
    • 업로드한 파일은 <b>서버에 저장되지 않으며</b>, 분석 후 즉시 폐기됩니다.<br><br>
    <b>샘플 파일</b>로 먼저 테스트해보고 싶다면 아래에서 내려받을 수 있어요 👇
    </div>
    """, unsafe_allow_html=True)

    st.download_button(
        "⬇ sample_book.xlsx 다운받기",
        SAMPLE_PATH.read_bytes(),
        file_name="sample_book.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
# ───────────────── 함수 정의 ───────────────── #
def preprocessing(df: pd.DataFrame) -> pd.DataFrame:
    """
    엑셀(나이스) 또는 CSV → 통일된 컬럼(id, name, section, year, grade, sem, book)
    """
    try:  # 나이스 엑셀 : 8행(인덱스 7)에 '번호' 헤더
        if df.iloc[7, 1] == "번호":
            # 1:번호(id) 2:이름 3:반 4:번호(학생번호) 6:학년 7:학기 8:도서
            df = df.iloc[8:, [1, 2, 3, 4, 6, 7, 8]]
        else:
            raise ValueError
    except Exception:  # CSV (헤더·열 구조가 다를 수 있음)
        if df.shape[1] >= 7:            # id 열까지 포함된 CSV
            df = df.iloc[3:, :7]
        else:                           # id 열 없는 CSV
            df = df.iloc[3:, :6]

    df.columns = ["id", "name", "section", "year", "grade", "sem", "book"][: df.shape[1]]

    # id 컬럼이 없으면 삽입
    if "id" not in df.columns:
        df.insert(0, "id", pd.NA)

    df = df.dropna(how="all").fillna(method="ffill")
    df = df[~df["name"].eq("성  명")].reset_index(drop=True)
    return df


kiwi = Kiwi()

def similarity(a: str, b: str) -> tuple[float, list[str]]:
    """형태소 기반 유사도(2.0: 완전일치), 공통 형태소도 반환"""
    t1 = [tok[0] for tok in kiwi.analyze(a)[0][0] if tok[0] not in ("(", ")")]
    t2 = [tok[0] for tok in kiwi.analyze(b)[0][0] if tok[0] not in ("(", ")")]
    sim = (len(t1) + len(t2)) / len(set(t1 + t2))
    common = list(set(t1) & set(t2))
    return sim, common

import difflib
def show_diff(text1, text2):
    diff = difflib.ndiff(text1, text2)
    diff_text = ""
    for c in diff:
        if c[0] == ' ':
            diff_text += c[2]
        elif c[0] == '-':
            diff_text += (
                "<span style='color: red; background-color: #ffeaea; "
                "font-weight: bold; font-size: 1.3em; text-decoration: line-through;'>"
                f"{c[2]}</span>"
            )
        elif c[0] == '+':
            if c[2] == ' ':
                diff_text += (
                    "<span style='color: blue; background-color: #ffffcc; "
                    "font-weight: bold; font-size: 1.3em;'>&nbsp;</span>"
                )
            else:
                diff_text += (
                    "<span style='color: blue; background-color: #ffffcc; "
                    "font-weight: bold; font-size: 1.3em;'>"
                    f"{c[2]}</span>"
                )
    return diff_text

def analyse(df: pd.DataFrame, cut: float) -> pd.DataFrame:
    """중복·유사 도서를 찾아 결과표 반환 (학생 + 번호 포함)."""
    records = []
    for _, row in df[["name", "id"]].drop_duplicates().iterrows():
        stu, sid = row["name"], row["id"]
        books = []
        for cell in df.loc[df["name"] == stu, "book"]:
            books += [b if b.endswith(")") else b + ")" for b in cell.split("), ") if b]
        for i in range(len(books)):
            for j in range(i + 1, len(books)):
                s, common = similarity(books[i], books[j])
                if s == 2.0:
                    records.append([stu, sid, "중복", s, books[i], books[j], common])
                elif s >= cut:
                    records.append([stu, sid, "유사", s, books[i], books[j], common])


    return pd.DataFrame(records, columns=["학생", "번호", "유형", "유사도", "도서A", "도서B", "공통형태소"]
    ).sort_values(by=["학생", "번호", "유사도"], ascending=[True, True, False]).reset_index(drop=True)

# ───────────────── 파일 업로더 ───────────────── #
uploaded = st.file_uploader("📄 파일 업로드 (.xlsx / .csv)", ("xlsx", "csv"))

# ────────── 유사도 기준 (라디오 100·80·60 %) ────────── #
st.markdown("### 🎯 **유사도 기준을 선택하세요**")
level = st.radio(
    label="도서명(저자)를 형태소 기준으로 모두 분리했을 때, 단어가 얼마나 겹치는 것을 살펴볼지 결정할 수 있습니다.",
    options=[
        "🟢  엄격  (100% 일치)",
        "🟡  권장  (80 % 일치)",
        "🔴  느슨  (60 % 일치)",
    ],
    index=1,
)

cut_percent = 100 if "100" in level else 60 if "60" in level else 80
cut_score   = cut_percent * 0.014 + 0.6   # 60→1.44, 80→1.72, 100→2.0

# ───────────────── 메인 로직 ───────────────── #
if uploaded:
    try:
        raw_df = pd.read_csv(uploaded, header=None) if uploaded.type == "text/csv" \
                else pd.read_excel(uploaded, header=None, engine="openpyxl")
        cleaned = preprocessing(raw_df)
        with st.expander("📊 원본 데이터 미리보기 (클릭)"):
            st.write(cleaned)  # 필요 시 주석 해제
    except Exception as e:
        st.error(f"파일을 읽을 수 없습니다 ▶ {e}")
        st.stop()

    with st.spinner("🔍 중복·유사 기록을 찾는 중입니다..."):
        result  = analyse(cleaned, cut_score)

    dup_cnt  = (result["유형"] == "중복").sum()
    sim_cnt  = (result["유형"] == "유사").sum()
    total    = len(result)

    # ────────────── 대시보드 출력 ────────────── #
    # ──────────── AFTER ────────────
    unique_students   = cleaned[["id", "name"]].drop_duplicates()
    total_students    = len(unique_students)

    dup_student_cnt   = result[result["유형"] == "중복"][["학생", "번호"]].nunique()["학생"]
    sim_student_cnt   = result[result["유형"] == "유사" ][["학생", "번호"]].nunique()["학생"]

    if total == 0:
        st.success(f"🎉 **중복·유사 기록이 없습니다!** (기준 {cut_percent} %)")
        st.metric("검사 학생 수", total_students)
        st.balloons()
    else:
        # st.success(f"✅ 중복 {dup_cnt}건 · 유사 {sim_cnt}건 (기준 {cut_percent} %)")

        # ── 요약 카드 ──
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 학생 수", total_students)
        c2.metric("중복 기록 학생", dup_student_cnt)
        c3.metric("유사 기록 학생", sim_student_cnt)


        # ── 결과 테이블 ──
        # st.dataframe(result, hide_index=True)


        # ── 학생·번호별 상세 출력 ── #
        for _, stu, sid in result[["학생", "번호"]].drop_duplicates().itertuples():
            sub = result[(result["학생"] == stu) & (result["번호"] == sid)]
            st.subheader(f"👤 {stu} ({sid}번)")
            for _, _, _, typ, simv, a, b, common in sub.itertuples():
                if typ == "중복":
                    st.error(f"😱 **중복** | {a}  ↔  {b}")
                else:
                    st.warning(f"⚠ **유사**({simv:.2f}) | {a}  ↔  {b}   \n   오타인지 확인해주세요.")

                    # if st.button("비교하기"):
                    diff_result = show_diff(a, b)
                    st.markdown(diff_result, unsafe_allow_html=True)


                    # st.caption("🔍 공통 형태소: " + ", ".join(common) if common else "없음")
                # 원본 행 미리보기
                origin = cleaned[
                    (cleaned["name"] == stu) &
                    (cleaned["id"] == sid) &
                    cleaned["book"].str.contains(a[:5], regex=False, na=False)   # ← 수정
                ]
                st.dataframe(origin.iloc[:, 1:], hide_index=True, height=120)
else:
    st.info("먼저 파일을 업로드해 주세요. (위의 샘플로 테스트 가능)")
# ────────────── Footer ────────────── #
# ────────────── Footer ────────────── #
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.9em; padding-top: 10px; line-height: 1.6;'>
        💡 made by <b>숩숩</b> · 
        <a href="https://surihub-rpa-app-ieocnc.streamlit.app/[%EC%83%9D%EA%B8%B0%EB%B6%80]%EB%8F%84%EC%84%9C%EC%A4%91%EB%B3%B5%EA%B8%B0%EC%9E%AC_%EC%B0%BE%EA%B8%B0" 
           target="_blank" style="color: lightgray; text-decoration: none;">
           원본 앱
        </a><br>
        이상이 있는 경우 메일로 연락주세요: 
        <a href="mailto:sbhath17@gmail.com">sbhath17@gmail.com</a>
    </div>
    """,
    unsafe_allow_html=True
)

