#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec2 uv;
layout(location=2) in vec4 colour;
layout(location=3) in float emission;
uniform mat4 vp;
out vec2 tex;
out vec4 tint;
out float glow;
out vec3 world;
void main(){gl_Position=vp*vec4(position,1);tex=uv;tint=colour;glow=emission;world=position;}
