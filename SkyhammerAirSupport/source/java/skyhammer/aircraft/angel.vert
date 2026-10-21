#version 330
layout(location=0) in vec3 position;
layout(location=1) in vec2 uv;
layout(location=2) in vec4 colour;
uniform mat4 vp;
out vec2 tex;
out vec4 tint;
out vec3 world;
void main(){
    gl_Position=vp*vec4(position,1);
    gl_Position.z=min(gl_Position.z,gl_Position.w*.999999);
    world=position;tex=uv;tint=colour;
}
