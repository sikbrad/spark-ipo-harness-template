# DD Bot 채널 인사말 중복 게시 원인 조사

- 작성일: 2026-06-26
- 요청: "온라인주문 > 일반 채널의 DD Bot 채팅 두 건은 왜 생겼나? 검토하고 리서치 문서 남겨라."
- 대상 메시지 2건 (모두 `온라인주문` 팀 / `일반` 채널):
  - [1780969238221](https://teams.microsoft.com/l/message/19:k6ce3VK8aJ9tPTpi12Z-dFv9mfeQVWHxCa5t2A8tqt01@thread.tacv2/1780969238221?tenantId=157be4ae-85e2-465d-b741-e92c2db1df96&groupId=14e77e8c-0ed8-42e7-9c65-62c44f4deb0f&parentMessageId=1780969238221) — 2026-06-09 10:40 KST
  - [1782445906474](https://teams.microsoft.com/l/message/19:k6ce3VK8aJ9tPTpi12Z-dFv9mfeQVWHxCa5t2A8tqt01@thread.tacv2/1782445906474?tenantId=157be4ae-85e2-465d-b741-e92c2db1df96&groupId=14e77e8c-0ed8-42e7-9c65-62c44f4deb0f&parentMessageId=1782445906474) — 2026-06-26 12:51 KST (오늘)

---

## 1. 결론 (TL;DR)

두 메시지는 **사람이 쓴 글이 아니라 DD Bot이 자동으로 뱉은 자기소개 인사말**이다. 본문은 두 건 모두 글자까지 동일하다:

> 안녕하세요. 저는 DD Bot(ㅇㅇ)입니다. 채널에서는 @DD Bot(ㅇㅇ)으로 멘션해 주시고, 1:1 채팅에서는 바로 메시지를 보내주세요.

원인은 DD Bot 코드의 `onMembersAdded` 핸들러다. **`온라인주문` 팀에 새 사람이 한 명 추가될 때마다**, Teams가 봇에게 `conversationUpdate / membersAdded` 이벤트를 (팀 기본 채널인 `일반` 채널 대화로) 보내고, 핸들러가 그 채널에 위 인사말을 게시한다.

- 6/9 인사말 = **서해리(전임연구원)** 가 팀에 합류(셀프 조인) → 트리거
- 6/26 인사말 = **백인식 부장(=사용자 본인)** 이 **박민수 과장**을 팀에 추가 → 트리거

즉, "왜 생겼나"의 답은 **버그성 동작**이다: 새 멤버 1:1 환영 인사로 의도된 듯한 메시지가, 실제로는 `일반` 채널 전체에 공개 브로드캐스트되고 사람이 추가될 때마다 반복 발생한다.

---

## 2. 증거 타임라인 (MS Graph 채널 메시지 raw)

`GET /teams/14e77e8c-.../channels/19:k6ce...@thread.tacv2/messages` 로 채널 전체(총 19건)를 조회한 결과. 인사말 직전 ~1초 시점에 항상 `membersAddedEventMessageDetail` 시스템 이벤트가 선행한다.

| 시각 (UTC) | 유형 | 내용 |
|---|---|---|
| 2026-06-02T09:07:26Z | `teamsAppInstalledEventMessageDetail` | DD Bot 앱이 팀에 **설치됨** — 인사말 **없음** |
| 2026-06-09T01:40:36.504Z | `membersAddedEventMessageDetail` | 멤버 추가: 서해리 |
| **2026-06-09T01:40:38.221Z** | `message` (from: **DD Bot**) | **인사말 #1** (멤버추가 +1.7초) |
| 2026-06-26T03:51:45.652Z | `membersAddedEventMessageDetail` | 멤버 추가: 박민수 |
| **2026-06-26T03:51:46.474Z** | `message` (from: **DD Bot**) | **인사말 #2** (멤버추가 +0.8초) |

추가 사실:
- 이 `일반` 채널에 DD Bot이 올린 메시지는 평생 **딱 2건뿐이며 둘 다 이 인사말**이다. 실제 주문 알림 등 업무 메시지는 다른 채널(`샵주문-자동화-회계관련`, `샵주문-자동화-개발관련`, `noti-order` 등)로 가고 `일반`에는 멤버추가 인사말만 쌓인다.
- 6/2 **앱 설치 이벤트**에는 인사말이 따라붙지 않았다 → 트리거는 "앱 설치"가 아니라 "멤버 추가"임을 역으로 증명한다 (아래 §4 참고).

### 멤버 추가 이벤트 상세 (who/who)

| 발생 | 추가된 사람 (members[].id) | 추가한 사람 (initiator) |
|---|---|---|
| 6/9 | 서해리 Haeri `333a504a-…` / haeri@doflab.com / 전임연구원 | 본인 (셀프 조인, initiator 동일) |
| 6/26 | 박민수 Allen `bf014773-…` / minsoo215@doflab.com / 과장 | 백인식 Brad `4bf9f38a-…` / ins@doflab.com / 부장 |

두 추가 멤버 모두 `userIdentityType: aadUser` 즉 **사람**이다 (봇 자기 추가가 아님).

---

## 3. 근본 원인 (코드)

- repo: `/Users/gq/works/projs/teams-bot/teams-bot-dofi-01`
- 봇 앱 ID: `63b88a07-a179-469d-880a-cc9298efcfc0` (manifest `name.short` = `DD Bot(ㅇㅇ)`, `developer.name` = DOF Inc.)
- 핸들러: `src/bot/dofiBot.ts:150`

```js
this.onMembersAdded(async (context, next) => {
  const activity = context.activity;
  const reference = TurnContext.getConversationReference(activity);
  upsertConversationFromActivity(activity, reference);

  const newcomers = context.activity.membersAdded ?? [];
  for (const member of newcomers) {
    if (member.id !== context.activity.recipient.id) {   // 추가된 멤버가 '봇 자신'이 아니면
      await context.sendActivity(                          // → 현재 대화(=일반 채널)에 인사말 게시
        `안녕하세요. 저는 DD Bot(ㅇㅇ)입니다. 채널에서는 @DD Bot(ㅇㅇ)으로 멘션해 주시고, 1:1 채팅에서는 바로 메시지를 보내주세요.`,
      );
    }
  }
  recordEvent('conversation.members.added', 'Members added event received', { ... });
  await next();
});
```

동작 정리:
1. Bot Framework `onMembersAdded`는 `conversationUpdate` + `membersAdded` 활동에서 실행된다.
2. 팀 스코프 봇의 경우 이 이벤트는 **팀 기본 채널(`일반`/General) 대화**로 전달된다.
3. 추가된 멤버가 봇 자신(`member.id === recipient.id`)이면 건너뛰고, **사람이면 인사말을 그 채널에 `sendActivity`** 한다.
4. `sendActivity(text)`는 새 멤버에게 1:1 DM이 아니라 **현재 대화(=공개 `일반` 채널)** 에 글을 올린다.

---

## 4. 왜 "설치"가 아니라 "멤버 추가"가 트리거인가

- 6/2 앱 설치 시점엔 인사말이 없었다. 일반적으로 팀에 봇이 설치될 때 Teams가 보내는 `membersAdded`에는 **봇 자신**이 담기는데, 위 코드의 `member.id !== recipient.id` 가드가 그 케이스를 걸러내므로 설치 자체로는 인사말이 안 나간다.
- 반대로 사람이 팀에 들어오면 `membersAdded`에 그 사람의 aadUser id가 담겨 가드를 통과 → 인사말이 `일반` 채널에 게시된다.
- 본 조사에서 6/9·6/26 두 인사말 모두 직전 1초 내 `membersAddedEventMessageDetail`(서해리 / 박민수)이 선행함을 확인했으므로, 트리거는 **사람 1명 팀 합류**로 확정된다.

---

## 5. 버그인가 의도인가 — 평가

핸들러 텍스트는 "1:1 채팅에서는 바로 메시지를 보내주세요"라고 안내한다. 즉 **새로 합류한 사람에게 봇 사용법을 알려주려는 온보딩 의도**로 보인다. 하지만 구현이 의도와 어긋난다:

1. **대상이 잘못됨** — 새 멤버 개인에게 1:1로 보내는 게 아니라 `일반` 채널 전체에 공개 게시된다. 그래서 기존 멤버 전원이 "또 그 인사말"을 보게 된다.
2. **반복 노이즈** — 사람이 한 명 추가될 때마다 매번 재발한다. 팀 인원이 늘수록 `일반` 채널에 동일 인사말이 계속 쌓인다.
3. **표준 패턴과 다름** — Bot Framework 권장 패턴은 (a) 봇 설치 시 팀에 1회 환영, (b) 새 유저는 개인 환영. 현재 코드는 둘 다 아닌 "멤버 추가마다 채널 브로드캐스트"다.

결론: **기능적 장애는 아니지만 UX 버그**. 사용자가 "왜 생겼냐"고 의아해한 것이 정상 반응이다.

---

## 6. 권고 (수정 옵션)

`teams-bot-dofi-01/src/bot/dofiBot.ts:150` 핸들러를 다음 중 하나로 정리하면 된다. (실제 수정은 봇 repo에서 별도 진행)

- **옵션 A — 인사말 비활성화(가장 단순):** 채널 멤버 추가에 대한 `sendActivity` 인사를 제거하고, `recordEvent`만 남긴다. `일반` 채널에 봇이 글 쓸 일이 없어진다.
- **옵션 B — 봇 설치 1회만 환영:** 조건을 표준 패턴(`member.id === recipient.id`, 즉 봇이 추가된 설치 시점)으로 바꿔 팀당 1회만 환영. 단, 봇 설치 이벤트가 채널에 공개되는 건 동일하니 톤을 "팀 환영" 문구로.
- **옵션 C — 새 멤버에게 1:1 DM:** 채널 브로드캐스트 대신 추가된 멤버에게 개인 채팅으로 온보딩 안내(proactive 1:1). 의도에 가장 부합하지만 proactive 설치/대화 생성 권한·로직이 필요.
- **옵션 D — 채널 스코프 가드:** `conversationType === 'channel'`이면 인사 생략하고 1:1(`personal`)에서만 인사. 최소 변경으로 채널 노이즈 제거.

권장: **옵션 A 또는 D** (가장 적은 변경으로 채널 노이즈 제거). 온보딩 안내가 꼭 필요하면 옵션 C.

---

## 7. 부록 — 재현/검증 방법

```python
import sys; sys.path.insert(0, 'proc/lib')
from msgraph import GraphClient
g = GraphClient()
team_id   = '14e77e8c-0ed8-42e7-9c65-62c44f4deb0f'   # 온라인주문
channel_id= '19:k6ce3VK8aJ9tPTpi12Z-dFv9mfeQVWHxCa5t2A8tqt01@thread.tacv2'  # 일반
# 인사말 + 직전 membersAdded 시스템 이벤트 확인
data = g.get(f'/teams/{team_id}/channels/{channel_id}/messages?$top=50')
# m['from']['application']['displayName']=='DD Bot', m['eventDetail']['@odata.type']에 'membersAdded'
```

핵심 식별자:
- 봇 앱 id: `63b88a07-a179-469d-880a-cc9298efcfc0`
- 6/9 추가 멤버: 서해리 `333a504a-e3bb-4b3f-b1e4-4e1202679d86`
- 6/26 추가 멤버: 박민수 `bf014773-cac3-4d0a-bee8-2f5137ea54fa`, 추가자: 백인식 `4bf9f38a-b3f8-4f9b-9e8a-691a0523d5c1`

관련 문서: [2026-06-11_makeshop_auto_order_generation_teams_investigation.md](../plan/2026-06-11_makeshop_auto_order_generation_teams_investigation.md) (DD Bot 운영/주문 자동화 맥락)

---

## 8. 조치 결과 (2026-06-26)

- **옵션 A 적용 + 운영 배포 완료** — `teams-bot/teams-bot-dofi-01/src/bot/dofiBot.ts`의 `onMembersAdded` 핸들러에서 채널 인사말 `sendActivity` 루프를 제거. 멤버 추가는 `recordEvent('conversation.members.added', …)`로 기록만 남긴다. `bun run check`(번들 빌드) 통과.
  - 배포: `DOF-AX01:/home/ax01/works/projs/teams-bot-dd-01/src/bot/dofiBot.ts`로 scp → 원격 `bun build` 검증 → `pm2 restart ddbot-api --update-env`. 런타임은 TS 직접 실행(`bun run src/bot/index.ts`)이라 별도 빌드 단계 없음.
  - 검증: 원격 파일 인사말 0건, `ddbot-api` online(↺19→20), 내부/공개 `/health` 모두 `{"ok":true,"name":"DD Bot(ㅇㅇ)","nodeEnv":"production"}`. 이제 팀에 새 멤버가 추가돼도 채널 인사말이 재발하지 않는다.
  - 미커밋: 봇 repo 로컬/원격 소스만 반영. git commit은 미실행(요청 시 진행).
- **메시지 4건 삭제 완료** — DD Bot이 작성한 글이라 사용자 Graph 토큰으로는 삭제 불가(작성자=봇). 봇 자체 API `POST https://ddbot-api.doflab.com/api/delete`로 삭제.
  - target은 `teamId+channelId`가 아니라 **`conversationId`(=채널 thread id)** 로 줘야 함. 멤버추가(팀 스코프) 이벤트로 upsert된 conversations 행은 `channel_id`가 null이라 `(team_id, channel_id)` 조회가 404가 난다 (`conversationId`로 조회하면 성공).
  - **인사말은 한 팀이 아니라 DD Bot이 설치된 모든 팀의 기본 채널에 발생**했다. 처음엔 사용자가 링크한 `온라인주문/일반` 2건만 지웠는데, 전체 sweep 결과 `DOF Inc./General`에도 2건이 더 있었다.
  - 삭제한 4건 (전부 Graph 재조회 404 = hard delete 확인):
    - `온라인주문/일반` (`19:k6ce…@thread.tacv2`): `1780969238221`(6/9), `1782445906474`(6/26)
    - `DOF Inc./General` (`19:cb59b09dcdc8474e9c26b8ae0e20c7d5@thread.skype`): `1781493583633`(6/15), `1782439887810`(6/26)
  - **최종 검증**: 가입 팀 5개 전체 채널 sweep → 잔존 live DD Bot 인사말 **0건**.
  - 교훈: 봇 자동 게시물 정리는 "사용자가 준 링크"가 아니라 **봇이 게시 가능한 전 범위(설치된 모든 팀·채널)를 sweep**해서 처리해야 한다.
