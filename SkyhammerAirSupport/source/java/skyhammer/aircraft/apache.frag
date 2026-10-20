#version 330
in vec3 vNormal,vColour,vPos;
in vec4 vCurrent,vPrevious;
flat in float vPart;
uniform vec3 uLight,uEye;
layout(location=0) out vec4 gAlbedo;
layout(location=1) out vec4 gNormal;
layout(location=2) out vec4 gLight;
layout(location=3) out vec4 gVelocity;
void main() {
    vec3 n=normalize(vNormal);
    if(dot(n,uEye-vPos)<0.)n=-n;
    gAlbedo=vec4(vColour,0.);
    gNormal=vec4(n,1.);
    gLight=vec4(clamp(uLight,0.,1.),1.);
    gVelocity=vec4(0.);
    if(vCurrent.w>0.0001 && vPrevious.w>0.0001)
        gVelocity=vec4((vCurrent.xy/vCurrent.w-vPrevious.xy/vPrevious.w)*.5,vPrevious.w,1.);
}
