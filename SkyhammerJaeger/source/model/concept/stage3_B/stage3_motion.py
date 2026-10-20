"""Original rigid mech choreography. Blender space: Z up / forward -Y."""
import math
from mathutils import Vector,Matrix,Quaternion
FPS=30
SPECS={
'J_Idle':{'duration':4.0,'loop':True,'keys':[0,1,2],'events':[]},
'J_Walk':{'duration':3.0,'loop':True,'keys':[0,.75,1.5,2.25],'events':[('foot_contact_L',0),('foot_contact_R',1.5)]},
'J_Drop':{'duration':2.5,'loop':False,'keys':[0,1.2,1.4,2.5],'events':[('landing',1.2),('stand_recovered',2.5)]},
'J_Stomp':{'duration':2.0,'loop':False,'keys':[0,.55,.9,1.15],'events':[('stomp_R',.9)]},
'J_Punch':{'duration':2.0,'loop':False,'keys':[0,.35,.7,1.2],'events':[('punch_L',.7)]},
'J_CannonOut':{'duration':1.0,'loop':False,'keys':[0,.33,.67,1.0],'events':[('armor_open',.33),('fist_stowed',.73),('cannon_ready',1.0)]},
'J_CannonFire':{'duration':1.0,'loop':False,'keys':[0,.3,.4,1.0],'events':[('fire',.3)]},
'J_CannonIn':{'duration':1.0,'loop':False,'keys':[0,.33,.67,1.0],'events':[('barrel_retracted',.32),('fist_restored',.70),('armor_closed',1.0)]},
'J_FinalCharge':{'duration':3.0,'loop':True,'keys':[0,1,2],'events':[]},
'J_FinalFire':{'duration':1.5,'loop':False,'keys':[0,.1,.23,1.5],'events':[('fire',.1)]},
'J_Lift':{'duration':3.0,'loop':False,'keys':[0,1.5,3.0],'events':[('lift_start',0),('lift_30m',3.0)]},
}
def smooth(t,a,b):
    u=max(0,min(1,(t-a)/(b-a)))
    return u*u*(3-2*u)
def pulse(t,start,peak,end):
    if t<=start or t>=end:return 0.
    return smooth(t,start,peak) if t<peak else 1-smooth(t,peak,end)
def rx(a):return Matrix.Rotation(a,3,'X')
def rz(a):return Matrix.Rotation(a,3,'Z')
def pose_matrix(position,rotation):
    m=rotation.to_4x4();m.translation=Vector(position);return m
def rotate_between(a,b):
    return Vector(a).normalized().rotation_difference(Vector(b).normalized()).to_matrix()
def ik2(h,target,l1,l2,pole):
    v=target-h;dist=v.length
    if dist>l1+l2+1e-5:raise AssertionError(('IK target out of reach',dist,l1+l2))
    d=min(l1+l2-1e-7,max(abs(l1-l2)+1e-7,dist));axis=v.normalized()
    a=(l1*l1-l2*l2+d*d)/(2*d);height=math.sqrt(max(0,l1*l1-a*a))
    pp=Vector(pole);perp=pp-axis*pp.dot(axis)
    if perp.length<1e-5:perp=Vector((1,0,0))-axis*axis.x
    return h+axis*a+perp.normalized()*height
class Choreography:
    def __init__(self,rests,parents,part_matrices):
        self.rest=rests;self.parents=parents;self.names=list(rests)
        self.pos={n:m.translation.copy() for n,m in rests.items()}
        self.rot={n:m.to_3x3() for n,m in rests.items()}
        self.parts=part_matrices
        self.leg={}
        for s in ['L','R']:
            h=self.pos[s+'_Thigh'];k=self.pos[s+'_Knee'];a=self.pos[s+'_Ankle']
            self.leg[s]=((k-h).length,(a-k).length)
        barrel=part_matrices['R_Plasma_BARREL_EMITTER']
        self.muzzle_rest_dir=(barrel.to_3x3()@Vector((0,0,-1))).normalized()
    def build(self,name,t):
        spec=SPECS[name];t=max(0,min(spec['duration'],t))
        P={};I=Matrix.Identity(3);body_shift=Vector((0,0,0))
        body_r=I.copy();chest_r=I.copy();pelvis_r=I.copy();chest_dz=0.
        cannon=False;cprog=0.;recoil=0.;big=0.
        if name=='J_Walk':
            p=t/3
            body_shift=Vector((.16*math.cos(2*math.pi*p),0,-.72+.08*(1-math.cos(4*math.pi*p))))
            chest_r=rx(.035)@rz(.025*math.cos(2*math.pi*p))
            pelvis_r=rz(-.018*math.cos(2*math.pi*p))
        elif name=='J_Drop':
            if t<1.2:body_shift.z=30*(1-(t/1.2)**2)
            elif t<=1.4:body_shift.z=-1.30*smooth(t,1.2,1.4)
            else:body_shift.z=-1.30*(1-smooth(t,1.4,2.5))
            chest_r=rx(.11*pulse(t,1.2,1.4,2.5))
        elif name=='J_Stomp':
            support=pulse(t,0,.5,1.9);shock=pulse(t,.9,1.03,1.65)
            body_shift=Vector((.23*support,0,-.25*support-.48*shock))
            chest_r=rx(.07*shock)
        elif name=='J_Punch':
            drive=pulse(t,.05,.7,1.85);wind=pulse(t,0,.30,.7)
            body_shift=Vector((.08*drive,.12*wind,-.36*drive))
            chest_r=rx(.035*drive)@rz(.11*wind-.13*drive)
        elif name in ['J_CannonOut','J_CannonIn','J_CannonFire','J_FinalCharge','J_FinalFire']:
            cannon=True
            cprog=t if name=='J_CannonOut' else 1-t if name=='J_CannonIn' else 1.
            body_shift.z=-.25*cprog;chest_r=rx(.025*cprog)
            if name=='J_CannonFire':
                recoil=pulse(t,.3,.4,.84)
                body_shift.y=.11*recoil;chest_r=rx(.025-.045*recoil)
            elif name in ['J_FinalCharge','J_FinalFire']:
                body_shift.z=-1.08
                chest_r=rx(.10)
                if name=='J_FinalCharge':
                    wave=math.sin(2*math.pi*t/3)
                    body_shift.z+=.018*wave;chest_r=rx(.10+.004*wave)
                else:
                    big=pulse(t,.1,.2333333333,1.15);recoil=big
                    body_shift.y=.40*big;body_shift.z-=.18*big
                    chest_r=rx(.10-.13*big)
        elif name=='J_Lift':
            body_shift.z=30*smooth(t,0,3)
        elif name=='J_Idle':
            wave=math.sin(2*math.pi*t/4);chest_dz=.028*wave;chest_r=rx(.004*wave)
        def child(n,rotation=None,shift=None):
            parent=self.parents[n]
            parent_delta=P[parent]@self.rest[parent].inverted() if parent else Matrix.Identity(4)
            m=parent_delta@self.rest[n]
            if shift is not None:m.translation+=parent_delta.to_3x3()@Vector(shift)
            if rotation is not None:
                m=pose_matrix(m.translation,parent_delta.to_3x3()@rotation@self.rot[n])
            P[n]=m;return m
        P['Dummy01']=self.rest['Dummy01'].copy()
        P['Translation_Data']=self.rest['Translation_Data'].copy()
        bp=self.pos['Body'];P['Body']=pose_matrix(bp+body_shift,body_r@self.rot['Body'])
        child('Pelvis',pelvis_r);child('Chest',chest_r,(0,0,chest_dz))
        child('Head',rx(-.5*math.atan2(chest_r[2][1],chest_r[2][2])))
        child('Reactor',rx(.003*math.sin(2*math.pi*t/spec['duration'])),(0,-.010*math.sin(2*math.pi*t/spec['duration']),0))
        child('cockpitCam')
        chest_delta=P['Chest']@self.rest['Chest'].inverted();cr=chest_delta.to_3x3()
        pelvis_delta=P['Pelvis']@self.rest['Pelvis'].inverted()
        feet={}
        for side,sign in [('L',1),('R',-1)]:
            child(side+'_Shoulder');child('hook_'+side)
            # Arms: separate shoulder cap, upper arm, elbow, forearm, hand, and booster.
            hn=side+'_UpperArm';en=side+'_Elbow';fn=side+'_Forearm';hand=side+'_Hand'
            h=chest_delta@self.pos[hn];u0=self.pos[en]-self.pos[hn];f0=self.pos[hand]-self.pos[en]
            up_angle=0.;low_angle=0.
            if name=='J_Walk':
                up_angle=sign*.20*math.cos(2*math.pi*t/3);low_angle=up_angle-.10
            elif name=='J_Idle':
                up_angle=sign*.007*math.sin(2*math.pi*t/4);low_angle=up_angle
            elif name=='J_Drop':
                low_angle=-.16*pulse(t,.92,1.4,2.5)
            elif name=='J_Stomp':
                up_angle=-.12*pulse(t,0,.55,1.7);low_angle=up_angle
            ur=cr@rx(up_angle);lr=cr@rx(low_angle)
            e=h+ur@u0
            if cannon and side=='R':
                arm_u=smooth(cprog,.08,.85)
                ready=cr@rx(-.38-(.10 if name.startswith('J_Final') else 0))
                ur=ur.to_quaternion().slerp(ready.to_quaternion(),arm_u).to_matrix()
                e=h+ur@u0
                # Stabilized aim: the barrel's physical axis points along model forward.
                aim=rx(-(.07 if name=='J_FinalFire' else .035)*recoil)@rotate_between(self.muzzle_rest_dir,Vector((0,-1,0)))
                lr=lr.to_quaternion().slerp(aim.to_quaternion(),arm_u).to_matrix()
            if name.startswith('J_Final') and side=='L':
                ur=cr@rx(-.32);lr=cr@rx(-.70);e=h+ur@u0
            if name=='J_Punch' and side=='L':
                # Wind-up, full extension at 0.7s, then recover.
                rest_w=self.pos[hand]-self.pos[hn]
                wind=Vector((.30,.96,-1.63))
                hit=Vector((.18,-4.45,-.83))
                if t<=.33:rel=rest_w.lerp(wind,smooth(t,0,.33))
                elif t<=.7:rel=wind.lerp(hit,smooth(t,.33,.7))
                else:rel=hit.lerp(rest_w,smooth(t,.7,1.8))
                w=h+cr@rel
                e=ik2(h,w,u0.length,f0.length,cr@Vector((1,.10,-.15)))
                ur=rotate_between(u0,e-h);lr=rotate_between(f0,w-e)
            else:w=e+lr@f0
            P[hn]=pose_matrix(h,ur@self.rot[hn])
            P[en]=pose_matrix(e,ur@self.rot[en])
            P[fn]=pose_matrix(e,lr@self.rot[fn])
            P[hand]=pose_matrix(w,lr@self.rot[hand])
            # A stabilized rear thruster follows the elbow's center while keeping a rearward nozzle.
            P[side+'_Booster']=pose_matrix(e,cr@self.rot[side+'_Booster'])
            if side=='R':
                fd=P[fn]@self.rest[fn].inverted()
                opening=smooth(cprog,.06,.33);fold=smooth(cprog,.30,.63)
                retract=smooth(cprog,.43,.73);extend=smooth(cprog,.68,1.0)
                for n,angle in [('R_Forearm_hinge_UPPER',-math.radians(52)*opening),('R_Forearm_hinge_LOWER',math.radians(62)*opening)]:
                    P[n]=fd@self.rest[n]@Matrix.Rotation(angle,4,'X')
                n='R_FIST_RETRACTABLE'
                P[n]=fd@self.rest[n]@Matrix.Translation(Vector((0,.70*retract,.85*retract)))@Matrix.Rotation(math.radians(108)*fold,4,'X')
                n='R_Plasma_BARREL_EMITTER'
                stroke=1.28*extend-(.30 if name=='J_FinalFire' else .16)*recoil
                P[n]=fd@self.rest[n]@Matrix.Translation(Vector((0,0,-stroke)))
                child('muzzle_R')
            # Analytic two-link leg targets: exact sole height during all grounded phases.
            child(side+'_Hip')
            hn=side+'_Thigh';kn=side+'_Knee';sn=side+'_Shin';an=side+'_Ankle';ft=side+'_Foot'
            h=pelvis_delta@self.pos[hn];k0=self.pos[kn];a0=self.pos[an];h0=self.pos[hn]
            target=a0.copy();foot_r=I.copy();use_ik=False
            if name=='J_Walk':
                p=(t/3+(0 if side=='L' else .5))%1
                if p<.5:forward=2.25-9*p;lift=0.
                else:
                    u=(p-.5)*2
                    forward=-2.25*(2*u**3-3*u*u+1)-4.5*(u**3-2*u*u+u)+2.25*(-2*u**3+3*u*u)-4.5*(u**3-u*u)
                    lift=.95*math.sin(math.pi*u)**2
                target.y=a0.y-forward;target.z=a0.z+lift;use_ik=True
            elif name=='J_Drop':
                if t<1.2:target.z+=body_shift.z
                use_ik=True
            elif name=='J_Stomp':
                if side=='R':
                    lift=2.15*(smooth(t,0,.55) if t<.55 else 1-smooth(t,.55,.9)) if t<.9 else 0.
                    target.z+=lift;target.y-=.70*pulse(t,0,.55,1.5)
                use_ik=True
            elif name in ['J_Punch','J_CannonOut','J_CannonIn','J_CannonFire','J_FinalCharge','J_FinalFire']:
                if name.startswith('J_Final'):target.x=sign*2.82
                use_ik=True
            elif name=='J_Lift':
                hang=smooth(t,.18,1.1)
                target.x=(1-hang)*a0.x+hang*(h.x+sign*.29)
                length=sum(self.leg[side])
                target.z=(1-hang)*(a0.z+body_shift.z)+hang*(h.z-math.sqrt((length-.012)**2-.29**2))
                target.y=(1-hang)*a0.y+hang*(h.y+.015)
                foot_r=rx(.15*smooth(t,.40,1.2));use_ik=True
            if use_ik:
                l1,l2=self.leg[side]
                d=(target-h).length
                rest_axis=(a0-h0).normalized()
                rest_pole=k0-h0-rest_axis*(k0-h0).dot(rest_axis)
                # Straight/rest poses retain the original outward knee bend; crouches bend forward.
                amount=min(1,max(0,(sum(self.leg[side])-d-.015)/.35))
                pole=rest_pole.normalized().lerp(Vector((0,-1,0)),amount)
                knee=ik2(h,target,l1,l2,pole)
                tr=rotate_between(k0-h0,knee-h);sr=rotate_between(a0-k0,target-knee)
                kr=tr.to_quaternion().slerp(sr.to_quaternion(),.5).to_matrix()
                P[hn]=pose_matrix(h,tr@self.rot[hn]);P[kn]=pose_matrix(knee,kr@self.rot[kn])
                P[sn]=pose_matrix(knee,sr@self.rot[sn])
                P[an]=pose_matrix(target,foot_r@self.rot[an]);P[ft]=pose_matrix(target,foot_r@self.rot[ft])
            else:
                child(hn);child(kn);child(sn);child(an);child(ft)
            feet[side]=P[ft].translation.copy()
        assert set(P)==set(self.rest),(set(self.rest)-set(P),set(P)-set(self.rest))
        return P
