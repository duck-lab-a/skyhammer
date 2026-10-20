import java.nio.*;import java.nio.file.*;import java.io.*;
import org.lwjgl.BufferUtils;import org.lwjgl.glfw.GLFW;import org.lwjgl.opengl.*;
import org.joml.Matrix4f;
public class A10GLTest {
 static int shader(int type,String source){int s=GL20.glCreateShader(type);GL20.glShaderSource(s,source);GL20.glCompileShader(s);if(GL20.glGetShaderi(s,GL20.GL_COMPILE_STATUS)==0)throw new AssertionError(GL20.glGetShaderInfoLog(s));return s;}
 static void mat(int p,String key,Matrix4f m){FloatBuffer b=BufferUtils.createFloatBuffer(16);m.get(b);GL20.glUniformMatrix4fv(GL20.glGetUniformLocation(p,key),false,b);}
 static void scalar(int p,String key,float x){GL20.glUniform1f(GL20.glGetUniformLocation(p,key),x);}
 static void check(boolean b,String s){if(!b)throw new AssertionError(s);}
 static float read(int attachment){GL11.glReadBuffer(GL30.GL_COLOR_ATTACHMENT0+attachment);FloatBuffer b=BufferUtils.createFloatBuffer(128*128*4);GL11.glReadPixels(0,0,128,128,GL11.GL_RGBA,GL11.GL_FLOAT,b);float m=0;for(int i=0;i<b.capacity();i+=4){check(Float.isFinite(b.get(i)),"finite G-buffer");m=Math.max(m,Math.abs(b.get(i)));}return m;}
 public static void main(String[] args)throws Exception{
  Path root=Path.of(args[0]);check(GLFW.glfwInit(),"GLFW");GLFW.glfwWindowHint(GLFW.GLFW_VISIBLE,GLFW.GLFW_FALSE);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MAJOR,3);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MINOR,3);
  long w=GLFW.glfwCreateWindow(128,128,"A10 hidden shader validation",0,0);check(w!=0,"context");GLFW.glfwMakeContextCurrent(w);GL.createCapabilities();
  int p=GL20.glCreateProgram();GL20.glAttachShader(p,shader(GL20.GL_VERTEX_SHADER,Files.readString(root.resolve("a10.vert"))));GL20.glAttachShader(p,shader(GL20.GL_FRAGMENT_SHADER,Files.readString(root.resolve("aircraft.frag"))));GL20.glLinkProgram(p);check(GL20.glGetProgrami(p,GL20.GL_LINK_STATUS)!=0,GL20.glGetProgramInfoLog(p));GL20.glUseProgram(p);
  int fbo=GL30.glGenFramebuffers();GL30.glBindFramebuffer(GL30.GL_FRAMEBUFFER,fbo);
  int[] attachments=new int[4];for(int i=0;i<4;i++){int t=GL11.glGenTextures();GL11.glBindTexture(GL11.GL_TEXTURE_2D,t);GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,GL30.GL_RGBA16F,128,128,0,GL11.GL_RGBA,GL11.GL_FLOAT,(ByteBuffer)null);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_NEAREST);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_NEAREST);attachments[i]=GL30.GL_COLOR_ATTACHMENT0+i;GL30.glFramebufferTexture2D(GL30.GL_FRAMEBUFFER,attachments[i],GL11.GL_TEXTURE_2D,t,0);}
  int depth=GL30.glGenRenderbuffers();GL30.glBindRenderbuffer(GL30.GL_RENDERBUFFER,depth);GL30.glRenderbufferStorage(GL30.GL_RENDERBUFFER,GL14.GL_DEPTH_COMPONENT24,128,128);GL30.glFramebufferRenderbuffer(GL30.GL_FRAMEBUFFER,GL30.GL_DEPTH_ATTACHMENT,GL30.GL_RENDERBUFFER,depth);GL20.glDrawBuffers(attachments);check(GL30.glCheckFramebufferStatus(GL30.GL_FRAMEBUFFER)==GL30.GL_FRAMEBUFFER_COMPLETE,"FBO");
  int n;FloatBuffer vertices;try(DataInputStream in=new DataInputStream(Files.newInputStream(root.resolve("a10.mesh")))){check(in.readInt()==0x53484131,"mesh");n=in.readInt();vertices=BufferUtils.createFloatBuffer(n*10);for(int i=0;i<n*10;i++)vertices.put(in.readFloat());vertices.flip();}
  GL30.glBindVertexArray(GL30.glGenVertexArrays());GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,GL15.glGenBuffers());GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L);}
  GL11.glViewport(0,0,128,128);GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDisable(GL11.GL_CULL_FACE);GL11.glClearColor(0,0,0,0);
  Matrix4f vp=new Matrix4f().ortho(-.22f,.22f,-.22f,.22f,.01f,20).lookAt(-.18f,-.46f,11,-.18f,-.46f,7.56f,0,1,0);
  mat(p,"uMvp",vp);mat(p,"uPlain",vp);mat(p,"uPrevious",vp);mat(p,"uModel",new Matrix4f());GL20.glUniform3f(GL20.glGetUniformLocation(p,"uBarrelAxis"),-.18f,-.46f,7.56f);GL20.glUniform3f(GL20.glGetUniformLocation(p,"uEye"),-.18f,-.46f,11);GL20.glUniform3f(GL20.glGetUniformLocation(p,"uLight"),.6f,.6f,.6f);scalar(p,"uFlash",0);scalar(p,"uPrevSpin",0);scalar(p,"uSpin",.18f);
  GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,n);float velocity=read(3);check(velocity>.001,"rotating-barrel velocity");check(read(0)>0,"airframe G-buffer");
  float[] flash={-.8f,-.8f,0,0,0,1,1,.72f,.22f,5, .8f,-.8f,0,0,0,1,1,.72f,.22f,5, 0,.8f,0,0,0,1,1,.72f,.22f,5};GL15.glBufferData(GL15.GL_ARRAY_BUFFER,flash,GL15.GL_STATIC_DRAW);mat(p,"uMvp",new Matrix4f());mat(p,"uPlain",new Matrix4f());mat(p,"uPrevious",new Matrix4f());
  GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,3);float hidden=read(0);scalar(p,"uFlash",1);GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,3);float shown=read(0);check(hidden==0&&shown>.9,"flash gate");check(GL11.glGetError()==0,"GL error");
  System.out.printf(java.util.Locale.ROOT,"{\"pass\":true,\"shader_link\":true,\"gbuffer_attachments\":4,\"barrel_velocity_max\":%.6f,\"flash_hidden\":%.1f,\"flash_shown\":%.1f,\"gpu\":\"%s\"}%n",velocity,hidden,shown,GL11.glGetString(GL11.GL_RENDERER));GLFW.glfwDestroyWindow(w);GLFW.glfwTerminate();
 }
}
