import java.nio.*;
import java.nio.file.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.util.*;
import org.lwjgl.BufferUtils;
import org.lwjgl.glfw.GLFW;
import org.lwjgl.opengl.*;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import skyhammer.aircraft.Nuke;

/** Hidden-context prototype: same procedural Nuke samples intended for the game renderer. */
public class NukePreview {
 static final int W=1920,H=1080;
 static int program,ground,vao,vbo,count;
 static boolean spriteMode;
 static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
 static int shader(int kind,String text){
  int s=GL20.glCreateShader(kind);GL20.glShaderSource(s,text);GL20.glCompileShader(s);
  if(GL20.glGetShaderi(s,GL20.GL_COMPILE_STATUS)==0)throw new IllegalStateException(GL20.glGetShaderInfoLog(s));return s;
 }
 static int program(String v,String f){
  int p=GL20.glCreateProgram();GL20.glAttachShader(p,shader(GL20.GL_VERTEX_SHADER,v));GL20.glAttachShader(p,shader(GL20.GL_FRAGMENT_SHADER,f));GL20.glLinkProgram(p);
  if(GL20.glGetProgrami(p,GL20.GL_LINK_STATUS)==0)throw new IllegalStateException(GL20.glGetProgramInfoLog(p));return p;
 }
 static void mat(int p,String key,Matrix4f m){matrix.clear();m.get(matrix);GL20.glUniformMatrix4fv(GL20.glGetUniformLocation(p,key),false,matrix);}
 static void vec(int p,String key,Vector3f x){GL20.glUniform3f(GL20.glGetUniformLocation(p,key),x.x,x.y,x.z);}
 static void upload(List<Nuke.Puff> p,Vector3f eye,Vector3f target){
  Vector3f f=new Vector3f(target).sub(eye).normalize(),r=new Vector3f(f).cross(0,1,0).normalize(),u=new Vector3f(r).cross(f).normalize();
  p.sort((a,b)->Float.compare((b.x()-eye.x)*f.x+(b.y()-eye.y)*f.y+(b.z()-eye.z)*f.z,(a.x()-eye.x)*f.x+(a.y()-eye.y)*f.y+(a.z()-eye.z)*f.z));
  FloatBuffer vertices=BufferUtils.createFloatBuffer(p.size()*6*10);
  float[][] corners={{-1,-1},{1,-1},{1,1},{-1,-1},{1,1},{-1,1}};
  for(Nuke.Puff a:p){
   double c=Math.cos(a.angle()),s=Math.sin(a.angle());
   for(float[] q:corners){
    // Rotate UV only: vertical illumination stays world-up while noise can vary by tile.
    float x=q[0]*a.rx(),y=q[1]*a.ry();
    vertices.put(a.x()+r.x*x+u.x*y).put(a.y()+r.y*x+u.y*y).put(a.z()+r.z*x+u.z*y);
    vertices.put((a.tile()%4+(q[0]+1)*.5f)/4).put((a.tile()/4+(1-q[1])*.5f)/2);
    vertices.put(a.r()).put(a.g()).put(a.b()).put(a.alpha()).put(a.emissive());
   }
  }
  vertices.flip();count=p.size()*6;GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STREAM_DRAW);
 }
 static void draw(Matrix4f vp,Vector3f eye){
  GL20.glUseProgram(program);mat(program,"vp",vp);vec(program,"eye",eye);
  GL20.glUniform1f(GL20.glGetUniformLocation(program,"fogScale"),spriteMode?0:1);
  GL11.glEnable(GL11.GL_BLEND);GL14.glBlendFuncSeparate(GL11.GL_SRC_ALPHA,GL11.GL_ONE_MINUS_SRC_ALPHA,GL11.GL_ONE,GL11.GL_ONE_MINUS_SRC_ALPHA);
  GL11.glDepthMask(false);GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);GL11.glDepthMask(true);
 }
 static void background(Matrix4f vp,Vector3f eye,boolean ortho){
  GL11.glDisable(GL11.GL_BLEND);GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(true);
  GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);
  GL20.glUseProgram(ground);mat(ground,"inv",new Matrix4f(vp).invert());mat(ground,"vp",vp);vec(ground,"eye",eye);
  GL11.glDrawArrays(GL11.GL_TRIANGLES,0,3);
 }
 static void save(Path file)throws Exception{
  ByteBuffer pixels=BufferUtils.createByteBuffer(W*H*4);GL11.glReadPixels(0,0,W,H,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,pixels);
  BufferedImage image=new BufferedImage(W,H,BufferedImage.TYPE_INT_RGB);
  int[] rgb=new int[W*H];for(int y=0;y<H;y++)for(int x=0;x<W;x++){
   int at=((H-1-y)*W+x)*4;rgb[y*W+x]=((pixels.get(at)&255)<<16)|((pixels.get(at+1)&255)<<8)|(pixels.get(at+2)&255);
  }
  image.setRGB(0,0,W,H,rgb,0,W);ImageIO.write(image,"png",file.toFile());
 }
 public static void main(String[] args)throws Exception{
  Path root=Path.of(args[0]),out=root.getParent().resolve("fx_art");
  if(!GLFW.glfwInit())throw new IllegalStateException("GLFW initialization");
  GLFW.glfwWindowHint(GLFW.GLFW_VISIBLE,GLFW.GLFW_FALSE);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MAJOR,3);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MINOR,3);
  long window=GLFW.glfwCreateWindow(W,H,"Skyhammer nuclear preview (hidden)",0,0);if(window==0)throw new IllegalStateException("GL context");
  GLFW.glfwMakeContextCurrent(window);GL.createCapabilities();
  String gpu=GL11.glGetString(GL11.GL_RENDERER);
  program=program(Files.readString(root.resolve("nuke_preview.vert")),Files.readString(root.resolve("nuke_preview.frag")));
  ground=program("""
   #version 330 core
   out vec2 uv;
   void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p*2-1;gl_Position=vec4(uv,0,1);}
   ""","""
   #version 330 core
   in vec2 uv;out vec4 result;uniform mat4 inv,vp;uniform vec3 eye;
   void main(){
    vec4 a=inv*vec4(uv,-1,1),b=inv*vec4(uv,1,1);vec3 p=a.xyz/a.w,d=normalize(b.xyz/b.w-p);
    float t=-p.y/d.y;vec3 sky=mix(vec3(.40,.46,.49),vec3(.19,.26,.31),clamp(d.y,0,1));
    result=vec4(sky,1);gl_FragDepth=1;
    if(t>0 && d.y<0){
     vec3 q=p+d*t;float dist=length(q-eye);float fog=1-exp(-dist*.0017);
     vec2 g=abs(fract(q.xz/50.-.5)-.5)/max(fwidth(q.xz/50.),vec2(.0001));
     float line=1-min(min(g.x,g.y),1);vec3 col=mix(vec3(.19,.205,.18),vec3(.25,.27,.23),line*.45);
     float burn=1-smoothstep(32.,65.,length(q.xz));col=mix(col,vec3(.09,.085,.075),burn*.7);
     result=vec4(mix(col,vec3(.40,.46,.49),fog),1);vec4 clip=vp*vec4(q,1);gl_FragDepth=(clip.z/clip.w)*.5+.5;
    }
   }
   """);
  vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
  int[] dims={3,2,4,1};int offset=0;for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,dims[i],GL11.GL_FLOAT,false,40,offset);offset+=dims[i]*4;}
  BufferedImage atlas=ImageIO.read(out.resolve("nuke_smoke_atlas.png").toFile());ByteBuffer tex=BufferUtils.createByteBuffer(atlas.getWidth()*atlas.getHeight()*4);
  for(int y=0;y<atlas.getHeight();y++)for(int x=0;x<atlas.getWidth();x++){int p=atlas.getRGB(x,y);tex.put((byte)(p>>16)).put((byte)(p>>8)).put((byte)p).put((byte)(p>>24));}tex.flip();
  GL13.glActiveTexture(GL13.GL_TEXTURE0);GL11.glBindTexture(GL11.GL_TEXTURE_2D,GL11.glGenTextures());GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,GL11.GL_RGBA8,atlas.getWidth(),atlas.getHeight(),0,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,tex);
  GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_LINEAR);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_LINEAR);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,GL12.GL_CLAMP_TO_EDGE);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,GL12.GL_CLAMP_TO_EDGE);
  int fbo=GL30.glGenFramebuffers();GL30.glBindFramebuffer(GL30.GL_FRAMEBUFFER,fbo);int color=GL11.glGenTextures();GL11.glBindTexture(GL11.GL_TEXTURE_2D,color);GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,GL11.GL_RGBA8,W,H,0,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,(ByteBuffer)null);GL30.glFramebufferTexture2D(GL30.GL_FRAMEBUFFER,GL30.GL_COLOR_ATTACHMENT0,GL11.GL_TEXTURE_2D,color,0);
  int depth=GL30.glGenRenderbuffers();GL30.glBindRenderbuffer(GL30.GL_RENDERBUFFER,depth);GL30.glRenderbufferStorage(GL30.GL_RENDERBUFFER,GL14.GL_DEPTH_COMPONENT24,W,H);GL30.glFramebufferRenderbuffer(GL30.GL_FRAMEBUFFER,GL30.GL_DEPTH_ATTACHMENT,GL30.GL_RENDERBUFFER,depth);
  if(GL30.glCheckFramebufferStatus(GL30.GL_FRAMEBUFFER)!=GL30.GL_FRAMEBUFFER_COMPLETE)throw new IllegalStateException("FBO");
  // The atlas was the first texture generated in this context.
  GL11.glBindTexture(GL11.GL_TEXTURE_2D,1);GL11.glViewport(0,0,W,H);GL11.glDisable(GL11.GL_CULL_FACE);
  if(args.length>1&&args[1].equals("sprites")){
   spriteMode=true;GL11.glViewport(0,0,512,512);GL11.glClearColor(0,0,0,0);
   Vector3f eye=new Vector3f(480,530,480),target=new Vector3f(0,145,0);
   Matrix4f vp=new Matrix4f().ortho(-225,225,-225,225,1,5000).lookAt(eye,target,new Vector3f(0,1,0));
   for(int i=0;i<24;i++){
    double e=.08+7.92*i/23.;List<Nuke.Puff> p=Nuke.sample(e,1,false);
    upload(p,eye,target);GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);draw(vp,eye);
    ByteBuffer bytes=BufferUtils.createByteBuffer(512*512*4);GL11.glReadPixels(0,0,512,512,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,bytes);
    BufferedImage im=new BufferedImage(512,512,BufferedImage.TYPE_INT_ARGB);
    for(int y=0;y<512;y++)for(int x=0;x<512;x++){
     int k=((511-y)*512+x)*4,a=bytes.get(k+3)&255;int rgba=a<<24;
     if(a>0)for(int j=0;j<3;j++)rgba|=Math.min(255,Math.round((bytes.get(k+j)&255)*255f/a))<<(16-j*8);
     im.setRGB(x,y,rgba);
    }
    ImageIO.write(im,"png",out.resolve(String.format("SH_FX_NukeCloud_%02d.png",i)).toFile());
   }
   GLFW.glfwDestroyWindow(window);GLFW.glfwTerminate();return;
  }
  StringBuilder rows=new StringBuilder();int maxTris=0;
  for(String mode:new String[]{"400m","2000m","quarter"})for(double e:new double[]{.2,1,3,8,30,75}){
   Vector3f eye=mode.equals("quarter")?new Vector3f(480,530,480):new Vector3f(0,1.6f,mode.equals("400m")?400:2000);
   Vector3f target=new Vector3f(0,145,0);Matrix4f vp=mode.equals("quarter")?new Matrix4f().ortho(-430,430,-242,242,1,5000):new Matrix4f().perspective((float)Math.toRadians(52),W/(float)H,.1f,10000);
   vp.lookAt(eye,target,new Vector3f(0,1,0));
   long start=System.nanoTime();List<Nuke.Puff> p=Nuke.sample(e,1);double generationMs=(System.nanoTime()-start)/1e6;
   for(Nuke.Puff a:p)if(!Float.isFinite(a.x()+a.y()+a.z()+a.rx()+a.ry()+a.alpha()))throw new AssertionError("nonfinite particle");
   upload(p,eye,target);maxTris=Math.max(maxTris,count/3);
   for(int i=0;i<12;i++){background(vp,eye,mode.equals("quarter"));draw(vp,eye);}GL11.glFinish();
   double[] ms=new double[40];int query=GL15.glGenQueries();
   for(int i=0;i<ms.length;i++){
    background(vp,eye,mode.equals("quarter"));GL15.glBeginQuery(GL33.GL_TIME_ELAPSED,query);draw(vp,eye);GL15.glEndQuery(GL33.GL_TIME_ELAPSED);
    ms[i]=GL33.glGetQueryObjectui64(query,GL15.GL_QUERY_RESULT)/1e6;
   }
   GL15.glDeleteQueries(query);Arrays.sort(ms);String t=e==Math.rint(e)?String.valueOf((int)e):String.valueOf(e);
   save(out.resolve("nuke_preview_"+mode+"_"+t+"s.png"));
   if(rows.length()>0)rows.append(",\n");rows.append(String.format(Locale.ROOT,"{\"view\":\"%s\",\"time_s\":%.1f,\"triangles\":%d,\"cpu_sample_ms_cold\":%.4f,\"gpu_ms_median\":%.4f,\"gpu_ms_p95\":%.4f}",mode,e,count/3,generationMs,ms[20],ms[38]));
   System.out.printf(Locale.ROOT,"%s %.1fs: %d triangles, GPU median %.3f ms, p95 %.3f ms%n",mode,e,count/3,ms[20],ms[38]);
  }
  boolean empty=Nuke.sample(-1,1).isEmpty()&&Nuke.sample(90,1).isEmpty();
  int error=GL11.glGetError();
  Files.writeString(out.resolve("nuke_preview_validation.json"),"{\n\"stage\":\"preview_only_not_integrated\",\n\"gpu\":\""+gpu+"\",\n\"resolution\":[1920,1080],\n\"max_triangles\":"+maxTris+",\n\"inactive_outside_lifetime\":"+empty+",\n\"gl_error\":"+error+",\n\"performance_scope\":\"isolated sorted billboard draw, hidden OpenGL context; excludes full game, TAA, G-buffer integration and CPU upload\",\n\"measurements\":["+rows+"]\n}");
  GLFW.glfwDestroyWindow(window);GLFW.glfwTerminate();if(error!=0||!empty)throw new AssertionError("validation");
 }
}
