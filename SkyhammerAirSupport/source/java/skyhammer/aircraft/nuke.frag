#version 330
in vec2 tex;in vec4 tint;in float glow;in vec3 world;
uniform sampler2D atlas,farDepth;
uniform mat4 invFar;
uniform vec3 eye,light;
uniform vec2 resolution;
uniform bool hasFar;
out vec4 result;
float distanceAt(float depth,vec2 uv,mat4 inverse){
 vec4 q=inverse*vec4(uv*2-1,depth*2-1,1);
 return length(q.xyz/q.w-eye);
}
void main(){
 vec4 s=texture(atlas,tex);float alpha=s.a*tint.a;
 if(alpha<.002)discard;
 vec2 screen=gl_FragCoord.xy/resolution;
 float d=length(world-eye);
 if(hasFar){float fd=texture(farDepth,screen).r;if(fd<.999999 && distanceAt(fd,screen,invFar)+1.<d)discard;}
 vec3 c=tint.rgb*mix(s.rgb,vec3(1),glow);
 c=pow(max(c,vec3(0)),vec3(2.2))*mix(clamp(light,vec3(.08),vec3(1)),vec3(3),glow);
 float fog=1-exp(-d*.00018);
 c=mix(c,vec3(.13,.18,.21)*max(light,vec3(.08)),fog*(1-.65*glow));
 result=vec4(c,alpha);
}
