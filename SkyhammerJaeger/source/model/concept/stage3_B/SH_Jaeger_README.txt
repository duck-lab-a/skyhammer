SKYHAMMER B — 3단계 최종 에셋

핵심 파일
- SH_Jaeger.glb: 단일 스킨 메시 + 39개 뼈 + 11개 애니메이션
- SH_Jaeger_source.blend: 편집 원본. 95개 분리 부품, 통합 스킨 메시, 리그, 11개 액션
- Skyhammer_B_albedo_2048.png: 이전 단계와 동일한 2048×2048 텍스처
- SH_Jaeger_anims.json: 동작 길이, 이벤트 초/프레임, 발사 시 포구 좌표
- SH_Jaeger_validation.json: 최종 검증 결과
- SH_Jaeger_animation_overview.png: 전체 동작 대표 자세
- previews/: 동작별 정면·3/4 비교판 11장, 핵심 프레임 PNG 82장
- before_stage3/: 이전 단계 파일 32개 보존. 원본 파일과 SHA-256 일치 확인

모델/리그
삼각형 19,776개, 뼈 39개, 단일 스킨 메시, 단일 머티리얼.
모든 정점은 한 개의 뼈에 100% 가중치. 발광 머티리얼 없음.
기존 93개 오브젝트의 이름과 원점을 유지하고 L_Knee_guard / R_Knee_guard 추가.
좌우 정강이 6개 부품의 하단 폭을 줄임. 나머지 87개 기존 부품의 형상과 기존 UV/텍스처 유지.
편집 원본의 SKYHAMMER_B_PARTS 컬렉션은 숨겨진 STOWED 기준 부품.
이 컬렉션을 표시할 때 SH_Jaeger_SKIN을 숨기면 중복 표시를 피할 수 있음.
부품별 rigid_bone 속성에 연결 뼈 이름 기록.

좌표와 계층
최종 GLB: 미터, Y 위, 정면 +Z, 원점은 두 발 사이 바닥, 기준 높이 15m.
Blender 원본: Blender 표준 Z 위 / 정면 -Y. GLB 작성 시 축 변환 적용.
Dummy01 → Translation_Data → Body. 그 아래 신체/소켓/캐논 뼈 배치.
Dummy01과 Translation_Data는 모든 동작에서 고정.
J_Drop과 J_Lift의 수직 이동은 Body에만 적용.
muzzle_R의 로컬 +Y가 발사 방향. 발사 프레임에서 모델 정면 +Z와 일치.
캐논 변형 네 뼈는 기존 해당 오브젝트의 원점에서 작동.

애니메이션
30fps. 프레임 0이 시간 0초. 일반 동작은 제자리.
J_Walk은 좌우 연속 착지 사이 4.5m 보폭(한 주기 9m, 환산 이동 속도 3m/s).
인게임 전진 이동은 게임 측 제어로 적용.
J_Idle / J_Walk / J_FinalCharge는 시작과 끝 자세가 같은 루프.
J_CannonFire와 J_FinalCharge/J_FinalFire는 캐논 전개 상태에서 시작.
J_CannonIn은 캐논 전개 동작의 역순.
전환 간 블렌딩과 게임 이벤트 연결은 게임 측에서 설정.
낙하·인양 비교판은 자세를 크게 볼 수 있도록 카메라가 Body 높이를 따라 이동.
각 프레임 제목에 Body의 기준 높이 대비 이동량 표시.

검증
GLB 바이너리, 뼈 계층, 역바인드 행렬, 강체 가중치, 모든 30fps 샘플의 바닥 관통,
루프 일치, 30m 낙하/인양, 4.5m 보폭, 발사 좌표를 검사.
Blender에서 GLB를 다시 가져와 메시/뼈/11개 액션을 확인하고 미리보기 렌더.
원본 액션과 제작 포즈의 최대 행렬 오차는 0.00001145 이하.
외부 모델·텍스처를 가져오지 않은 자체 제작 에셋.
Project Zomboid 게임 내 로더/애니메이션 연결 및 실제 게임 플레이 검증은 수행하지 않음.
