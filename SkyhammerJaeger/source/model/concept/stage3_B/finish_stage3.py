from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,hashlib,math
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'preview_manifest.json').read_text())
meta=json.loads((ROOT/'SH_Jaeger_anims.json').read_text())
report=json.loads((ROOT/'SH_Jaeger_validation.json').read_text())
build=json.loads((ROOT/'stage3_build_report.json').read_text())
audit=json.loads((ROOT/'stage3_blend_audit.json').read_text())
roundtrip=json.loads((ROOT/'stage3_roundtrip_verified.json').read_text())
def font(size):return ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',size)
bg=(23,26,31);fg=(228,233,240);muted=(165,177,191);orange=(255,158,55)
labels={'J_Idle':'대기 / 4초 루프','J_Walk':'걷기 / 3초 루프','J_Drop':'공수 낙하 / 2.5초','J_Stomp':'오른발 내려찍기 / 2초','J_Punch':'왼팔 추진 펀치 / 2초','J_CannonOut':'캐논 전개 / 1초','J_CannonFire':'캐논 발사 / 1초','J_CannonIn':'캐논 수납 / 1초','J_FinalCharge':'최종 사격 준비 / 3초 루프','J_FinalFire':'최종 사격 / 1.5초','J_Lift':'공중 인양 / 3초'}
event_labels={'foot_contact_L':'왼발 착지','foot_contact_R':'오른발 착지','landing':'착지','stand_recovered':'기립 완료','stomp_R':'내려찍기','punch_L':'펀치 타격','armor_open':'경첩 열림','fist_stowed':'주먹 수납','cannon_ready':'포신 전개 완료','barrel_retracted':'포신 수납','fist_restored':'주먹 복귀','armor_closed':'장갑 닫힘','fire':'발사','lift_start':'인양 시작','lift_30m':'30m 인양 완료'}
sheets=[]
for clip,info in meta['animations'].items():
 rows=[m for m in manifest if m['clip']==clip];times=sorted({m['frame'] for m in rows})
 w=480*len(times);h=1668
 canvas=Image.new('RGB',(w,h),bg);d=ImageDraw.Draw(canvas)
 d.text((24,15),clip+'  |  '+labels[clip],font=font(32),fill=fg)
 d.text((24,61),'최종 GLB 재가져오기 렌더  ·  30 fps  ·  위: 정면 / 아래: 3/4',font=font(21),fill=muted)
 for col,frame in enumerate(times):
  for row,view in enumerate(['front','threequarter']):
   m=next(m for m in rows if m['frame']==frame and m['view']==view)
   im=Image.open(ROOT/'previews'/m['file']).convert('RGB');assert im.size==(480,720)
   x=col*480;y=140+row*744;canvas.paste(im,(x,y))
  time_s=frame/30
  header=f'{time_s:.2f}s  /  F{frame:03d}'
  if clip in ['J_Drop','J_Lift']:
   m=next(m for m in rows if m['frame']==frame)
   header+=f"  Body {m['body_vertical_offset_m']:+.1f}m"
  d.text((col*480+16,101),header,font=font(23),fill=orange)
 events='  ·  '.join(f"{event_labels.get(e['name'],e['name'])} {e['time_s']:.2f}s" for e in info['events'])
 footer=events or '루프의 시작과 끝 자세 일치 확인'
 if clip in ['J_Drop','J_Lift']:footer+='  |  공중 자세 확인을 위해 카메라가 높이를 따라 이동'
 # Fit dense footer.
 size=20
 while d.textbbox((0,0),footer,font=font(size))[2]>w-48:size-=1
 d.text((24,1631),footer,font=font(size),fill=muted)
 path=ROOT/'previews'/f'{clip}_contact_sheet.png';canvas.save(path);sheets.append(path.name)
# Overview: representative poses across all 11 clips.
chosen={'J_Idle':0,'J_Walk':22,'J_Drop':42,'J_Stomp':16,'J_Punch':21,'J_CannonOut':30,'J_CannonFire':12,'J_CannonIn':20,'J_FinalCharge':30,'J_FinalFire':7,'J_Lift':90}
cw,ch=300,504;overview=Image.new('RGB',(cw*4,ch*3+104),bg);d=ImageDraw.Draw(overview)
d.text((24,15),'SKYHAMMER B  /  STAGE 3',font=font(36),fill=fg)
d.text((24,63),'39 bones  ·  19,776 triangles  ·  11 clips  ·  rigid skin',font=font(23),fill=orange)
for i,(clip,frame) in enumerate(chosen.items()):
 x=(i%4)*cw;y=104+(i//4)*ch
 m=next(m for m in manifest if m['clip']==clip and m['frame']==frame and m['view']=='threequarter')
 im=Image.open(ROOT/'previews'/m['file']).convert('RGB').resize((300,450),Image.Resampling.LANCZOS)
 overview.paste(im,(x,y))
 d.text((x+10,y+454),clip,font=font(22),fill=fg)
 d.text((x+10,y+479),labels[clip],font=font(17),fill=muted)
overview.save(ROOT/'SH_Jaeger_animation_overview.png')
# Consolidate independent checks into the user-facing validation JSON.
assert audit['baked_pose_max_matrix_error']<2e-5
assert roundtrip['skin_mesh_count']==1 and roundtrip['bone_count']==39 and len(roundtrip['action_names'])==11
assert len(manifest)==82 and len(sheets)==11
report['source_blend']={'file':'SH_Jaeger_source.blend','editable_named_parts':95,'existing_93_names_origins_preserved':build['original_93_names_origins_preserved'],'unchanged_original_part_geometry':87,'shin_tapered_parts':6,'new_knee_guards':build['new_parts'],'baked_pose_max_matrix_error':audit['baked_pose_max_matrix_error']}
report['roundtrip']={'blender_import':'PASS','skin_meshes':1,'bones':39,'animation_count':11,'rigid_weights_verified':True}
report['previews']={'render_source':'Final GLB re-import','individual_png_frames':82,'views':['front','threequarter'],'contact_sheets':sheets,'overview':'SH_Jaeger_animation_overview.png','camera_follows_vertical_motion':['J_Drop','J_Lift']}
(ROOT/'SH_Jaeger_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
readme='''SKYHAMMER B — 3단계 최종 에셋

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
'''
(ROOT/'SH_Jaeger_README.txt').write_text(readme,encoding='utf-8')
deliverables=['SH_Jaeger.glb','SH_Jaeger_source.blend','Skyhammer_B_albedo_2048.png','SH_Jaeger_anims.json','SH_Jaeger_validation.json','SH_Jaeger_animation_overview.png','SH_Jaeger_README.txt']
hashes={n:{'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in deliverables}
(ROOT/'SH_Jaeger_manifest.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print('DELIVERY_READY',len(sheets),'contact sheets',len(manifest),'frames')
