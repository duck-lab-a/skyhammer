#version 330
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNormal;
layout(location=2) in vec3 aColour;
layout(location=3) in float aPart;
uniform mat4 uMvp,uPlain,uPrevious,uModel;
uniform float uSpin,uPrevSpin;
uniform vec3 uBarrelAxis;
out vec3 vNormal,vColour,vPos;
out vec4 vCurrent,vPrevious;
flat out float vPart;
vec3 deform(vec3 p,float angle,bool position){
    if(abs(aPart-1.)>.1)return p;
    vec3 pivot=position?uBarrelAxis:vec3(0.);
    p-=pivot;
    float c=cos(angle),s=sin(angle);
    p.xy=mat2(c,s,-s,c)*p.xy;
    return p+pivot;
}
void main(){
    vec3 p=deform(aPos,uSpin,true);
    gl_Position=uMvp*vec4(p,1.);
    vCurrent=uPlain*vec4(p,1.);
    vPrevious=uPrevious*vec4(deform(aPos,uPrevSpin,true),1.);
    vNormal=mat3(uModel)*deform(aNormal,uSpin,false);
    vPos=(uModel*vec4(p,1.)).xyz;
    vColour=aColour;vPart=aPart;
}
