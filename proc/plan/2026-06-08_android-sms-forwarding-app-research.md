# Android SMS forwarding app 리서치 계획

작성일: 2026-06-08 KST

## 목적

회사 소유 Android 휴대폰에서 특정 발신번호의 SMS를 감지해 서버로 전달하고, 앱 동작 상태를 heartbeat로 보고하는 Android 앱 구현 가능성을 조사한다.

## 범위

- Android 앱 구현 방식: React Native, Expo Go, Expo development build, 네이티브 Android 코드
- SMS 수신 권한과 Google Play/Android 제한
- 백그라운드 동작, 재부팅 후 복구, heartbeat 설계
- 서버 API 상세 구현은 제외

## 진행 기록

- 2026-06-08: 기존 `proc/research` 문서 형식 확인.
- 2026-06-08: Android/Expo/Google Play 공식 문서 기준으로 가능성 및 제약 조사.
- 2026-06-08: 리서치 문서를 `proc/research/2026-06-08_android-sms-forwarding-app-research.md`에 저장.

## 결론 요약

- Expo Go만으로는 불가하다. SMS 수신은 Android manifest, runtime permission, `BroadcastReceiver`, WorkManager 같은 네이티브 레이어가 필요하다.
- Expo를 쓰려면 Expo development build + local Expo module/config plugin 방식이 현실적이다. 순수 React Native bare Android도 가능하다.
- 앱의 핵심 수신부는 JS보다 Kotlin/Java 네이티브 쪽에 두는 편이 안정적이다.
- heartbeat는 `WorkManager` periodic task 기준 15분 이상, 정확한 주기 보장 없음으로 설계해야 한다.
