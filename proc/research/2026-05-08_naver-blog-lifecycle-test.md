# 네이버 블로그 라이프사이클 테스트 (write → edit → delete)

## 목적

`pwc_naver.py` helper의 글 라이프사이클 전부 검증. 특히 `delete_post`는 아직 미구현이라 본 작업에서 신규 추가.

## 진행 로그

### [01] 시작 — 2026-05-08

기존 검증 완료:
- `write_post` ✅ logNo `224278980125`
- `edit_post` (텍스트만) ✅
- `publish_markdown` ✅
- `edit_markdown` ✅ logNo `224278993119` (cooking↔AX 글, 이미지 2장 inline)

남은 검증:
- `delete_post` — helper에 함수 자체가 없음. 본 작업에서 신규 구현.

### [02] Naver 블로그 삭제 UI 조사 — 결과

테스트 결과 채택 경로: **PostView 페이지(`/{blog_id}/{log_no}`) iframe 내부 본인-only 삭제 링크**.

- 에디터의 "더보기" dropdown — `새 글쓰기 / 내 블로그 / 관리 / 통계 / 기본 서체 설정` (삭제 없음). 탈락.
- `https://admin.blog.naver.com/{id}/post/list` — 404. URL 패턴 변경됨. 탈락.
- **`https://blog.naver.com/{id}/{log_no}` PostView** → `iframe#mainFrame` 내부에 본인 글이면 `<a class="btn_del _deletePost _returnFalse _param({logNo}|...)">삭제하기</a>` 노출. 클릭 시 native confirm "삭제된 글은 복구할 수 없습니다. 삭제하시겠습니까?" → accept → backend API 호출 → URL이 logNo 없는 blog root로 redirect.
  - 다음 방문 시 native alert "게시물이 삭제되었거나 다른 페이지로 변경되었습니다." 발생 — 멱등성 신호로 활용 가능.

### [03] delete_post 구현

`pwc_naver.py`에 추가:
- `_is_post_deleted(s, log_no, blog_id)` — `/{id}/{log_no}` 방문 후 URL에 logNo가 없으면 (= 삭제로 redirect됨) True.
- `delete_post(s, log_no, blog_id)`:
  1. `_is_post_deleted` 사전 체크 (멱등 — 이미 삭제됨이면 즉시 True)
  2. `_safe_goto`로 post URL 진입 + `_drain_modal`
  3. iframe poll (최대 ~10s) — `a._deletePost` 중 `_param({logNo}|...)` 매칭 링크 검색 + 클릭
  4. 다이얼로그 auto-accept (전역 핸들러)
  5. `_is_post_deleted`로 검증 — True면 성공, 아니면 PWCError

#### 핵심 보강 — 다이얼로그 자동 수락 핸들러

문제: Naver SmartEditor는 `addEventListener('beforeunload')`를 등록해 매 navigation마다 native "Leave site?" dialog를 띄움. 추가로 delete 시 confirm + 이미-삭제된-post 방문 시 alert가 줄줄이 발생. JS로 listener 제거 불가능.

해결: `_install_dialog_auto_accept(s)` — playwright-cli `run-code`로 세션의 `page.on('dialog', d => d.accept())`를 등록. 멱등 (window 센티넬 사용). `ensure_login`에서 매 진입 시 호출 → 모든 native modal이 사용자에게 보이지 않고 auto-accept됨.

```python
# pwc_naver.py
def _install_dialog_auto_accept(s):
    s.raw('run-code', "async () => { if (page.__naverAutoDialog) return ...;"
                      " page.__naverAutoDialog = true;"
                      " page.on('dialog', async d => { try { await d.accept(); } catch(e) {} });"
                      " return 'installed'; }")
```

이게 들어가기 전엔 `delete_post`가 함수 자체는 raise해도 dialog 드레인 사이드이펙트로 실제 삭제는 일어나는 비정상 동작이었음 (logNo `224279043127`, `224279051391`, `224279056354` — 세 번 같은 패턴).

### [04] 라이프사이클 라이브 검증 — 완료

logNo `224279062556` (private, 자동 생성):

```
[1] publish_markdown(lifecycle-v1.md)        -> 224279062556
[2] read_post                                title='라이프사이클 검증 — v1 (작은 자동화의 즐거움)'
[3] edit_markdown(224279062556, v2.md)       -> 224279062556 (same)
[4] read_post                                title='라이프사이클 검증 — v2 (수정 버전, 곧 삭제됨)'
[5] delete_post(224279062556)                -> True
[6] read_post                                title=None, body_len=0
```

전 단계 깨끗 통과. dialog 핸들러 덕분에 사용자가 "Leave site?" 직접 클릭할 일 없음.

### [05] 결론

`pwc_naver.py`의 글 라이프사이클 4종 전부 검증 완료:
- `publish_markdown` ✅
- `read_post` ✅
- `edit_markdown` ✅
- `delete_post` ✅ (신규 추가)

추가로 도출된 영구 패턴:
- 모든 `-s=naver` 작업 시작 시 `_install_dialog_auto_accept`를 호출. 사용자에게 "Leave site?" 같은 모달이 보이지 않음.
- 멱등 검증 (`_is_post_deleted`)으로 dialog 사이드이펙트 상황에서도 안정 동작.

세션 영속화(`--persistent`) + dialog 자동 수락 + iframe content polling — 이 세 가지가 합쳐져야 안정적.
