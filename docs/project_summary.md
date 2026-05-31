# Project Summary

본 프로젝트는 라즈베리파이와 Firebase Realtime Database를 활용하여 우산 보관함의 상태를 실시간으로 관리하는 스마트 우산 공유 시스템입니다.

## 핵심 기능

- 웹 기반 로그인, 대여, 예약, 반납 기능
- Firebase Realtime Database를 통한 실시간 보관함 상태 동기화
- Raspberry Pi 기반 솔레노이드 잠금장치 제어
- 푸쉬 스위치를 이용한 우산 유무 감지
- 반납 시 냉각팬을 이용한 간단한 건조 기능
- 지도 및 날씨 API를 활용한 사용자 편의 기능 설계

## 상태 정의

- `D`: Dry / 대여 가능
- `W`: Wet / 반납 후 건조 중
- `N`: None / 비어 있음
