#version 330
in vec2 tex;
in vec4 tint;
in vec3 world;
uniform sampler2D farDepth;
uniform mat4 invFar;
uniform vec3 eye,light;
uniform vec2 resolution;
uniform bool hasFar,core;
out vec4 result;
float hash(vec2 p){
    vec3 q=fract(vec3(p.xyx)*.1031);
    q+=dot(q,q.yzx+33.33);
    return fract((q.x+q.y)*q.z);
}
float noise(vec2 p){
    vec2 i=floor(p),v=fract(p);v=v*v*(3.-2.*v);
    return mix(mix(hash(i),hash(i+vec2(1,0)),v.x),
               mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),v.x),v.y);
}
void main(){
    vec2 screen=gl_FragCoord.xy/resolution;
    if(hasFar){
        float fd=texture(farDepth,screen).r;
        if(fd<.999999){
            vec4 q=invFar*vec4(screen*2-1,fd*2-1,1);
            if(length(q.xyz/q.w-eye)+.2<length(world-eye))discard;
        }
    }
    float a;
    vec3 c;
    if(core){
        float r=length(tex*2-1);
        if(tint.a<0.){
            r=abs(tex.x*2.-1.);
            a=pow(1.-smoothstep(0.,1.,r),2.)*(-tint.a)*(.45+.55*noise(world.xy*1.5+world.z*.7));
            c=tint.rgb*5.;
            if(a<.002)discard;
            result=vec4(c,a);return;
        }
        a=(1-smoothstep(.08,1.,r));
        a*=a*tint.a;
        c=tint.rgb*(3.+9.*(1.-smoothstep(0.,.24,r)));
    }else{
        vec2 q=tex*2.-1.;
        vec2 p=world.xy*.18+world.z*.11;
        float n=.65*noise(q*3.+p)+.35*noise(q*7.+p);
        float r=length(q);
        float density=1.-smoothstep(.12,.72+.28*n,r);
        a=density*tint.a*(.55+.70*n);
        c=tint.rgb*clamp(light,vec3(.23),vec3(1.))*(.80+.20*n);
    }
    if(a<.002)discard;
    result=vec4(c,a);
}
