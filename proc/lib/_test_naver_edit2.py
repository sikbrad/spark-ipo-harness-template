"""Edit existing post (224278993119) — replace with cooking↔AX analogy."""
from __future__ import annotations

import sys
import traceback

import pwc_naver as nb
from pwc import S

LOG_NO = 224278993119

NEW_TITLE = "요리와 AX의 닮은꼴 — 좋은 결과는 같은 원리에서 나온다"

NEW_BODY = """요리하는 과정과 AX(AI Transformation)를 추진하는 과정은 놀라울 정도로 닮았다. 표면은 다르지만 좋은 결과를 만드는 원리는 같다.

재료와 데이터.

좋은 요리의 시작은 신선한 재료다. AX의 시작은 깨끗한 데이터다. 시든 채소로는 일류 요리가 안 나오고, 오염된 데이터로는 신뢰할 모델이 안 나온다. 둘 다 시작 단계의 품질이 결과의 천장을 정한다.

레시피와 프로세스.

레시피는 단계의 순서와 비율을 정한다. AX의 프로세스는 작업의 순서와 책임을 정한다. 베테랑 셰프는 레시피를 상황에 맞게 변형할 줄 알고, 베테랑 PM은 프로세스를 현장에 맞게 조정할 줄 안다. 매뉴얼만 따라가는 셰프와 매뉴얼만 따라가는 팀은 똑같이 한계가 명확하다.

도구와 기술 스택.

잘 손에 맞는 칼은 요리의 효율을 결정한다. 적절한 LLM과 도구는 AX의 효율을 결정한다. 단, 비싼 칼이 모든 요리를 살리지 않는다. 최신 모델이 모든 문제를 해결하지도 않는다. 도구는 결과를 보장하지 않고, 다만 가능성의 범위를 넓힐 뿐이다.

맛과 사용자 경험.

결국 요리는 먹는 사람을 위한 것이고, AX는 사용자를 위한 것이다. 셰프 자신만 만족하는 요리는 식당에서 통하지 않는다. 개발팀만 만족하는 시스템도 현장에서 통하지 않는다. 만든 사람의 자기만족이 사용자의 만족과 일치한다고 생각하는 순간, 둘 다 무너진다.

마무리.

재료를 살리는 셰프와 데이터를 살리는 엔지니어. 도구를 다듬는 장인과 모델을 다듬는 연구자. 둘은 다른 영역에 있는 같은 부류의 장인이다. 잘하는 사람의 공통점은 한 가지다. 결과를 보는 게 아니라, 과정의 원리를 본다."""


def main() -> int:
    s = S("naver", persistent=True)
    print(f"[edit] log_no={LOG_NO}", flush=True)
    new_log_no = nb.edit_post(
        s,
        log_no=LOG_NO,
        title=NEW_TITLE,
        body=NEW_BODY,
        visibility="private",
        tags=["요리", "AX", "AI", "비유", "본질"],
    )
    print(f"    -> returned log_no = {new_log_no}", flush=True)

    print("[read after edit]", flush=True)
    post = nb.read_post(s, new_log_no)
    print(f"    title: {post.get('title')!r}", flush=True)
    print(f"    body[:200]: {post.get('body','')[:200]!r}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
