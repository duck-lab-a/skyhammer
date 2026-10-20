import skyhammer.aircraft.*;
import viewpoint.render.*;
import java.nio.*;import java.nio.file.*;import java.util.*;
import org.lwjgl.BufferUtils;import org.lwjgl.glfw.GLFW;import org.lwjgl.opengl.*;import org.joml.Matrix4f;

/** Real shipped renderer, synthetic depth targets. Does not launch or modify the game. */
public final class NukeRuntimeGLTest {
 static final int W=1920,H=1080;
 static FrameContext f;static Targets targets;static int farTex;
 static void check(boolean ok,String reason){if(!ok)throw new AssertionError(reason);}
 static int tex(int format,int external,int type){int t=GL11.glGenTextures();GL11.glBindTexture(GL11.GL_TEXTURE_2D,t);GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,format,W,H,0,external,type,(ByteBuffer)null);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_NEAREST);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_NEAREST);return t;}
 static void depth(float value){FloatBuffer d=BufferUtils.createFloatBuffer(W*H);for(int i=0;i<W*H;i++)d.put(value);d.flip();GL13.glActiveTexture(GL13.GL_TEXTURE0);GL11.glBindTexture(GL11.GL_TEXTURE_2D,farTex);GL11.glTexSubImage2D(GL11.GL_TEXTURE_2D,0,0,0,W,H,GL11.GL_RED,GL11.GL_FLOAT,d);}
 static void camera(float distance,boolean backwards){
  f.eyeX=0;f.eyeY=1.6f;f.eyeZ=distance;f.scene.projection.identity().perspective((float)Math.toRadians(52),W/(float)H,.05f,400);
  f.view=new Matrix4f().lookAt(0,1.6f,distance,0,145,backwards?distance+2000:0,0,1,0);
  f.scene.projection.mul(f.view,f.viewProjection);f.viewProjection.invert(f.invViewProjection);
  f.farNear=400;f.farFar=10000;
  new Matrix4f().perspective((float)Math.toRadians(52),W/(float)H,400,10000).mul(f.view).invert(f.farInvPlainViewProjection);
 }
 static void clear(double z){GL11.glDepthMask(true);GL11.glClearDepth(z);GL11.glClearColor(0,0,0,0);GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);}
 static void render(double time){AircraftBridge.nukeTick(time,0,0,0,1);NukeRenderer.capture(f,targets);NukeRenderer.allow(f);NukeRenderer.drawSafely(f.scene);}
 static float energy(){FloatBuffer p=BufferUtils.createFloatBuffer(W*H*4);GL11.glReadPixels(0,0,W,H,GL11.GL_RGBA,GL11.GL_FLOAT,p);float sum=0;for(int i=0;i<p.capacity();i+=4)sum+=p.get(i)+p.get(i+1)+p.get(i+2);return sum;}
 public static void main(String[] args)throws Exception{
  check(GLFW.glfwInit(),"GLFW");GLFW.glfwWindowHint(GLFW.GLFW_VISIBLE,GLFW.GLFW_FALSE);long win=GLFW.glfwCreateWindow(W,H,"hidden runtime FX validation",0,0);check(win!=0,"hidden context");GLFW.glfwMakeContextCurrent(win);GL.createCapabilities();
  Main.main(new String[0]);check(Main.supported,"Viewpoint signatures");
  f=new FrameContext();f.scene=new SceneData();f.width=W;f.height=H;f.scene.daylightKnown=true;f.scene.daylightR=f.scene.daylightG=f.scene.daylightB=.7f;
  // Allocate only this test's target descriptor: avoid constructing the entire Viewpoint renderer.
  java.lang.reflect.Field uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);sun.misc.Unsafe u=(sun.misc.Unsafe)uf.get(null);
  targets=(Targets)u.allocateInstance(Targets.class);
  int fb=GL30.glGenFramebuffers();GL30.glBindFramebuffer(GL30.GL_FRAMEBUFFER,fb);
  GL30.glFramebufferTexture2D(GL30.GL_FRAMEBUFFER,GL30.GL_COLOR_ATTACHMENT0,GL11.GL_TEXTURE_2D,tex(GL30.GL_RGBA16F,GL11.GL_RGBA,GL11.GL_FLOAT),0);
  int dt=tex(GL14.GL_DEPTH_COMPONENT24,GL11.GL_DEPTH_COMPONENT,GL11.GL_FLOAT);GL30.glFramebufferTexture2D(GL30.GL_FRAMEBUFFER,GL30.GL_DEPTH_ATTACHMENT,GL11.GL_TEXTURE_2D,dt,0);
  check(GL30.glCheckFramebufferStatus(GL30.GL_FRAMEBUFFER)==GL30.GL_FRAMEBUFFER_COMPLETE,"FBO");targets.depth=dt;
  farTex=tex(GL30.GL_R32F,GL11.GL_RED,GL11.GL_FLOAT);targets.farDepth=farTex;depth(1);
  GL11.glViewport(0,0,W,H);GL11.glDepthFunc(GL11.GL_LEQUAL);
  StringBuilder rows=new StringBuilder();
  for(float dist:new float[]{400,2000})for(double t:new double[]{.2,1,3,8,30,75}){
   camera(dist,false);for(int i=0;i<20;i++){clear(1);render(t);}GL11.glFinish();
   int q=GL15.glGenQueries();double[] gpu=new double[50],cpu=new double[50];
   for(int i=0;i<50;i++){
    clear(1);GL15.glBeginQuery(GL33.GL_TIME_ELAPSED,q);long start=System.nanoTime();render(t+i*.034);cpu[i]=(System.nanoTime()-start)/1e6;GL15.glEndQuery(GL33.GL_TIME_ELAPSED);gpu[i]=GL33.glGetQueryObjectui64(q,GL15.GL_QUERY_RESULT)/1e6;
   }
   GL15.glDeleteQueries(q);Arrays.sort(gpu);Arrays.sort(cpu);float energy=energy();check(energy>1,"visible at "+dist+" "+t);
   if(rows.length()>0)rows.append(",");rows.append(String.format(Locale.ROOT,"{\"distance\":%.0f,\"time\":%.1f,\"gpu_p95_ms\":%.4f,\"cpu_submit_p95_ms\":%.4f}",dist,t,gpu[47],cpu[47]));
   System.out.printf(Locale.ROOT,"%.0fm %.1fs GPU p95 %.3f ms CPU submit p95 %.3f ms%n",dist,t,gpu[47],cpu[47]);
  }
  camera(2000,false);clear(0);render(30);check(energy()==0,"near geometry occludes distant cloud");
  depth(0);clear(1);render(30);check(energy()==0,"far geometry occludes distant cloud");depth(1);
  camera(2000,true);clear(1);render(30);check(energy()==0,"behind-camera clip");
  camera(400,false);clear(1);AircraftBridge.nuke=new AircraftBridge.NukeSample(30,0,0,0,1,System.nanoTime()-60_000_000_000L);
  NukeRenderer.capture(f,targets);NukeRenderer.allow(f);NukeRenderer.drawSafely(f.scene);check(energy()>1,"paused combat clock stays visible");
  clear(1);AircraftBridge.nukeClear();NukeRenderer.capture(f,targets);NukeRenderer.allow(f);NukeRenderer.drawSafely(f.scene);check(energy()==0,"clear disables rendering");
  check(GL11.glGetError()==0,"GL errors");
  Files.writeString(Path.of(args[0]),"{\"pass\":true,\"gpu\":\""+GL11.glGetString(GL11.GL_RENDERER)+"\",\"resolution\":[1920,1080],\"near_occlusion\":true,\"far_occlusion\":true,\"beyond_400m\":true,\"behind_camera_clip\":true,\"clear\":true,\"scope\":\"shipped renderer and shaders in synthetic HDR/depth scene, CPU sample/sort/upload included; not a gameplay FPS measurement\",\"measurements\":["+rows+"]}");
  GLFW.glfwDestroyWindow(win);GLFW.glfwTerminate();
 }
}
