#version 330 core
in vec2 tex;in vec4 tint;in float glow;in vec3 world;
uniform sampler2D atlas;
uniform vec3 eye;
uniform float fogScale;
out vec4 result;
void main(){
 vec4 s=texture(atlas,tex);
 float alpha=s.a*tint.a;
 if(alpha<.002)discard;
 vec3 c=tint.rgb*mix(s.rgb,vec3(1),glow);
 float fog=1-exp(-length(world-eye)*.00018*fogScale);
 c=mix(c,vec3(.40,.46,.49),fog*(1-.65*glow));
 result=vec4(c,alpha);
}
