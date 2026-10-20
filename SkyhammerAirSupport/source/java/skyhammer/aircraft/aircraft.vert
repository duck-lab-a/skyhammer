#version 330
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNormal;
layout(location=2) in vec3 aColour;
layout(location=3) in float aPart;
uniform mat4 uMvp, uPlain, uPrevious, uModel;
uniform float uSpin, uPrevSpin;
out vec3 vNormal, vColour, vPos;
out vec4 vCurrent, vPrevious;
flat out float vPart;
vec3 rotateProp(vec3 p,float angle,bool position) {
    if(aPart<.5 || aPart>4.5) return p;
    float centers[4]=float[4](-12.,-6.,6.,12.);
    vec3 center=vec3(centers[int(aPart)-1],.9,7.6);
    if(position)p-=center;
    float c=cos(angle),s=sin(angle);
    p.xy=mat2(c,s,-s,c)*p.xy;
    if(position)p+=center;
    return p;
}
void main() {
    vec3 p=rotateProp(aPos,uSpin,true);
    gl_Position=uMvp*vec4(p,1.);
    vCurrent=uPlain*vec4(p,1.);
    vPrevious=uPrevious*vec4(rotateProp(aPos,uPrevSpin,true),1.);
    vNormal=mat3(uModel)*rotateProp(aNormal,uSpin,false);
    vPos=(uModel*vec4(p,1.)).xyz;
    vColour=aColour; vPart=aPart;
}
