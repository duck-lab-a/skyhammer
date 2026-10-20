#version 330
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNormal;
layout(location=2) in vec3 aColour;
layout(location=3) in float aPart;
uniform mat4 uMvp, uPlain, uPrevious, uModel;
// Radians: main rotor, tail rotor, turret yaw, barrel depression.
uniform vec4 uPose, uPreviousPose;
out vec3 vNormal, vColour, vPos;
out vec4 vCurrent, vPrevious;
flat out float vPart;
vec3 rx(vec3 p,float a) { float c=cos(a),s=sin(a); return vec3(p.x,c*p.y-s*p.z,s*p.y+c*p.z); }
vec3 ry(vec3 p,float a) { float c=cos(a),s=sin(a); return vec3(c*p.x+s*p.z,p.y,-s*p.x+c*p.z); }
vec3 deform(vec3 p,vec4 pose,bool position) {
    int part=int(aPart+.1);
    if(part==1) { vec3 c=position?vec3(0.,2.65,-.45):vec3(0.);return c+ry(p-c,pose.x); }
    if(part==2) { vec3 c=position?vec3(.48,1.05,-7.15):vec3(0.);return c+rx(p-c,pose.y); }
    if(part==4) { vec3 c=position?vec3(0.,-1.02,2.45):vec3(0.);p=c+rx(p-c,pose.w); }
    if(part==3 || part==4) { vec3 c=position?vec3(0.,-.73,2.45):vec3(0.);p=c+ry(p-c,pose.z); }
    return p;
}
void main() {
    vec3 p=deform(aPos,uPose,true);
    gl_Position=uMvp*vec4(p,1.);
    vCurrent=uPlain*vec4(p,1.);
    vPrevious=uPrevious*vec4(deform(aPos,uPreviousPose,true),1.);
    vNormal=mat3(uModel)*deform(aNormal,uPose,false);
    vPos=(uModel*vec4(p,1.)).xyz;
    vColour=aColour;vPart=aPart;
}
