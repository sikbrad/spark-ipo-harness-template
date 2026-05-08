# macOS 가상 데스크톱(Spaces) 전환 단축키 & 도구 조사

조사일: 2026-05-08
대상 OS: macOS Sonoma / Sequoia 기준 (Tahoe 포함, 거의 동일)

---

## 1. 용어 정리

- **Spaces**: macOS의 "가상 데스크톱". Mission Control 안에서 Desktop 1, Desktop 2 …로 표시.
- **Mission Control**: 모든 창과 Spaces를 한눈에 보는 화면 (Exposé의 후속).
- 윈도우 정렬(타일링)과는 별개 개념. 본 문서는 **Space 간 이동**에 집중.

---

## 2. macOS 기본 단축키 (네이티브)

### 2.1 Space 이동
| 동작 | 단축키 | 비고 |
|------|--------|------|
| 왼쪽 Space로 이동 | `Control + ←` | 기본 활성 |
| 오른쪽 Space로 이동 | `Control + →` | 기본 활성 |
| 특정 번호 Space로 점프 | `Control + 1` ~ `Control + 9` | **기본 비활성**, 수동 ON 필요 (아래 2.4 참고) |

### 2.2 Mission Control / 한눈에 보기
| 동작 | 단축키 |
|------|--------|
| Mission Control 열기 | `Control + ↑` 또는 `F3` (`fn+F3`) |
| Mission Control 닫기 | `Control + ↓` 또는 `Esc` |
| 앱별 창 모두 보기 (App Exposé) | `Control + ↓` |
| 데스크톱 보기 (창 모두 치우기) | `F11` 또는 `fn+F11` |

### 2.3 트랙패드 / 매직마우스 제스처
| 동작 | 제스처 |
|------|--------|
| Space 좌/우 이동 | 트랙패드: 3·4손가락 좌/우 스와이프 / 매직마우스: 2손가락 좌/우 스와이프 |
| Mission Control | 트랙패드: 3·4손가락 위로 스와이프 / 매직마우스: 2손가락 더블탭 |
| App Exposé | 3·4손가락 아래로 스와이프 |

> 트랙패드 손가락 수는 **System Settings → Trackpad → More Gestures**에서 3 또는 4로 변경 가능.

### 2.4 `Control + 숫자` 활성화 (중요)

Sonoma 이전에는 Space를 추가하면 자동으로 단축키가 잡혔지만, **Sequoia부터는 자동 등록이 안 되는 사례**가 보고됨. 수동 활성 절차:

1. **System Settings → Keyboard → Keyboard Shortcuts… → Mission Control**
2. 좌측 `Mission Control` 항목 옆 `>` 캐럿을 펼침
3. `Switch to Desktop 1`, `Switch to Desktop 2` … 항목 체크박스 ON
4. 필요 시 단축키를 클릭해 원하는 키 조합으로 변경 (예: `⌥⌘1`)

> 주의: 이 단축키 목록은 현재 존재하는 Space 개수만큼만 보임. 단축키를 미리 잡으려면 먼저 Mission Control에서 `+` 버튼으로 Desktop을 추가해야 함.

### 2.5 Space 관리

| 동작 | 방법 |
|------|------|
| Space 추가 | Mission Control 진입 후 우상단 `+` |
| Space 삭제 | Mission Control에서 썸네일에 마우스오버 → `X` |
| Space 순서 변경 | Mission Control에서 썸네일 드래그 |
| 앱을 특정 Space에 고정 | Dock의 앱 아이콘 우클릭 → Options → Assign To → This Desktop / All Desktops |

---

## 3. 흔한 함정

- **`Control + 숫자`가 안 먹힘**: 위 2.4 절차로 수동 활성. 일부 IDE(JetBrains 등)가 `Control + 숫자`를 가로채는 경우가 있어, 시스템 단축키를 `⌥⌘숫자`로 바꿔두는 게 충돌이 적음.
- **Space 전환 시 700ms 애니메이션**: macOS 자체 애니메이션이라 끄기 불가에 가까움. **System Settings → Accessibility → Display → Reduce motion** ON으로 단축은 됨.
- **`Displays have separate Spaces` 옵션**(System Settings → Desktop & Dock): OFF면 모든 모니터가 같이 전환, ON이면 모니터마다 독립적으로 Space 전환. 멀티모니터 사용 시 동작이 완전히 달라짐.
- Parallels / 가상머신 안에서 `Control + ←/→`을 OS가 가로채는 문제는 KB 118730 참고.

---

## 4. 서드파티 프로그램

### 4.1 Space/워크스페이스 전용

| 도구 | 특징 | 비고 |
|------|------|------|
| **BetterStage** | 이름 붙인 stage(가상 데스크톱) + BSP 자동 타일링 + 스냅 존. `Opt+1~9`로 16ms 이내 전환. SIP 비활성화/설정파일 불필요. | 유료, 가장 모던한 옵션 |
| **Spencer** | 저장한 레이아웃에 맞춰 Space 개수까지 자동 조정 (예: "개발" 레이아웃 = 4개, "글쓰기" = 2개) | 무료 |
| **VirtualSpaces.spoon** (Hammerspoon) | macOS Mission Control 전환 애니메이션을 회피하려는 가상 워크스페이스 시스템 | 무료, Hammerspoon 의존 |
| **TotalSpaces2** | 그리드 형태 Space 배치 + 단축키 풍부 | **macOS 12+에서 사실상 동작 불가**, 더 이상 추천 안 함 |

### 4.2 타일링 윈도우 매니저 (Space 전환도 강력)

| 도구 | 핵심 | 진입 비용 |
|------|------|-----------|
| **AeroSpace** | i3 스타일. **자체 가상 워크스페이스**를 구현해 macOS Space를 안 씀 → 전환 애니메이션 없음, SIP 비활성화 불필요 | 낮음~중. YAML 설정 |
| **yabai** | BSP 타일링 + 강력한 스크립팅. 풀 기능엔 SIP 일부 비활성 필요. `skhd`와 짝지어 단축키 정의 | 높음. 터미널 친화 사용자 추천 |
| **Amethyst** | 자동 타일링, 다양한 레이아웃. macOS Space를 그대로 사용 (= 700ms 애니메이션 그대로) | 낮음. SIP 변경 불필요 |

### 4.3 범용 자동화 / 단축키 도구

| 도구 | 용도 |
|------|------|
| **Hammerspoon** | Lua 스크립팅으로 macOS API 직접 제어. Space 이동 + 창 이동 + 조건부 트리거까지 모두 작성 가능. `hs.spaces` 모듈 또는 외부 `yabai` 호출 조합 |
| **Karabiner-Elements** | 키 리매핑. Caps Lock을 hyper key(⌥⌘⌃⇧)로 만들어 `hyper+1~9`를 Space 점프 단축키로 두는 패턴이 흔함 |
| **BetterTouchTool** | 트랙패드 제스처/단축키 커스터마이즈. "3손가락 모서리 탭 → Desktop 3" 같은 룰을 GUI로 만들기 좋음 |
| **Raycast** | 런처. Window Management 확장 + 직접 짠 스크립트로 Space 이동 |
| **skhd** | 가벼운 단축키 데몬. yabai 짝꿍으로 거의 항상 같이 쓰임 |

---

## 5. 추천 설정 (가벼운 사용자 / 파워 유저)

### 가벼운 사용자
1. Mission Control에서 Desktop을 원하는 개수만큼 미리 만든다.
2. **System Settings → Keyboard → Keyboard Shortcuts → Mission Control**에서 `Switch to Desktop 1~N`을 모두 ON.
3. 단축키 충돌 회피용으로 `⌃숫자` 대신 `⌥⌘숫자`로 변경.
4. **Reduce motion** ON으로 전환 애니메이션 단축.
5. 멀티모니터면 `Displays have separate Spaces` 본인 취향대로.

### 파워 유저
- **AeroSpace + Karabiner(hyper key)** 조합: SIP 안 건드리고 i3 스타일 워크스페이스. 학습곡선 낮음.
- 또는 **yabai + skhd**: 타일링까지 본격적으로 쓰고 싶을 때. SIP 일부 비활성 감수.
- **Hammerspoon**: 위 둘 어느 쪽이든 보조 자동화(앱별 자동 Space 배치, 알림 트리거)에 얹기.

---

## 6. 빠른 치트시트

```
Space 이동       : ⌃ + ←/→
번호로 점프      : ⌃ + 1~9   (수동 활성 필요)
Mission Control  : ⌃ + ↑     또는 F3
앱 Exposé        : ⌃ + ↓
데스크톱 보기    : F11
트랙패드         : 3/4손가락 좌우 스와이프 (Space) / 위 스와이프 (Mission Control)
```

---

## 출처

- [Work in multiple spaces on Mac - Apple Support](https://support.apple.com/guide/mac-help/work-in-multiple-spaces-mh14112/mac)
- [Keyboard Shortcuts to Switch Desktops in Sequoia - Apple Community](https://discussions.apple.com/thread/256054183)
- [MacOS Sequoia: Mission Control keyboard shortcuts - Apple Community](https://discussions.apple.com/thread/255840485)
- [How to switch directly to a MacOS desktop workspace with a hotkey - Chris Mavricos](https://chrismav.com/switch-workspace-hotkey/)
- [Mission Control 101: How to Use Multiple Desktops on a Mac - HowToGeek](https://www.howtogeek.com/180677/mission-control-101-how-to-use-multiple-desktops-on-a-mac/)
- [How to use multiple desktops on a Mac: 2026 update - Setapp](https://setapp.com/how-to/use-multiple-desktops-macos)
- [Tips for Using Mission Control on a Mac - OWC](https://eshop.macsales.com/blog/49131-tips-for-using-mission-control-on-a-mac/)
- [Best macOS Window Manager in 2026 — Complete Comparison - BetterStage](https://betterstage.app/best-macos-window-manager)
- [Best macOS Workspace Managers Compared (2026) - BRNSFT](https://www.brnsft.com/blog/best-macos-workspace-managers-compared-2026)
- [VirtualSpaces.spoon (GitHub)](https://github.com/brennovich/VirtualSpaces.spoon)
- [yabai (GitHub)](https://github.com/koekeishiya/yabai)
- [KB Parallels: Unable to switch desktops using shortcuts](https://kb.parallels.com/en/118730)
