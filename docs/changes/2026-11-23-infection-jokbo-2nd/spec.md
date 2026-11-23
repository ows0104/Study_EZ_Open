# 2차 판(2026-2) 만들기

```bash
python docs/changes/2026-11-23-infection-jokbo-2nd/build_source.py --report   # 원천 세트(source-2)
python -m runner.jokbo_solve build --edition 2026-2                          # 강의별 풀이 자료
python -m runner.jokbo_solve check <setId> --edition 2026-2                  # 해설·교정 검사
python -m runner.jokbo_solve upload --edition 2026-2 --audience all          # 러너 토큰이 있는 PC에서
```

## 원천 (`build_source.py`)

- 책 `~/amgi/2025 감염과 면역 족보.pdf`(SHA-256 e55ba879…1343)의 119~183쪽만 잘라 `source-2/book-2.pdf`로 두고
  amgi의 `parse_jokbo_pharm`·`build_pastexam_pharm`·pdfchange 이미지 추출을 그대로 돌린다(1차와 같은 도구, amgi 파일은 바꾸지 않음).
  잘라 낸 쪽 + 118 = 원본 쪽.
- 출력은 amgi와 같은 꼴(`source-2/data/pastexam/pes_infection-immunity-2-2026_<강의>.json`, `webapp/public/pastexam-figures/`).
- **강의 붙이기는 제목으로.** 책 머리 번호는 「2026년도 기준」이라 적혀 있지만 64~66이 올해 시간표와 다르다:
  책 64 호산구성 → 올해 66, 책 65 약물 알레르기 → 64, 책 66 다양한 알레르기질환 → 65. 나머지 49~63은 같다.
- 교수: 책 119쪽 표(열 26~20). 2025 = 25열. 칸마다 이름 하나라 열마다 맨 위 이름만 쓴다
  (표 아래 안내문이 마지막 줄 62 암면역에 이름처럼 붙어 읽혀서). 오타 「박홍우」 → 「박흥우」(64 호산구성 26·22열, 다른 칸은 모두 박흥우).
- 「체온 37.」 줄 끝 + 「0℃이다」 줄을 파서가 37번 문항으로 읽은 자리 2곳을 다시 붙인다
  (63 두드러기 2025 35번, 책 66 다양한 알레르기 2023 16번). 답안지에는 앞 번호만 있다.
- 책 자체 결함(문제 없이 답만 있음, 손대지 않음): 전신경화증 2025 14번(36번이 두 번 실림), 혈관염 2025 51번,
  알레르기 비염 2025 25번, 약물 알레르기 2025 57번. 혈관염 2025 21번은 문제만 있고 답안지에 답이 없다(채점 제외).
- 통풍 2023 답 10·21·53번은 답안지에 연도 머리가 「2022」로 잘못 적혀 있어 파서가 다른 해에서 이었다(`crossYearRescues`).

## 강의 자료 (`runner.jokbo_solve --edition 2026-2`)

- 판별 원천: `EDITIONS = {"2026-1": amgi, "2026-2": root/source-2}`. 해설·교정·중복 판정 폴더는 1차와 공용(세트 id가 다름).
- 올해 교수: 올해 필기 파일명 → 없으면 시간표. 2차 필기는 아직 없어 시간표 기준(`professorSource: timetable`).
- CBL 7~9(암면역·천식·류마티스관절염)에는 붙이지 않는다. 책에 CBL 구획이 없고 같은 주제 강의(62·60·52)에 이미 있다 —
  붙이면 모아풀기에서 같은 문항이 두 번 나온다.
- worktree가 저장소 옆 폴더(`../Study_EZ_<작업>`)여도 산출물은 원래 저장소의 `runs/`로 간다(`.git` 파일의 공용 git 폴더).
