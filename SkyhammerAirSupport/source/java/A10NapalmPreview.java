package skyhammer.aircraft;
import viewpoint.render.*;import java.nio.*;import java.nio.file.*;import java.awt.image.BufferedImage;import javax.imageio.ImageIO;
import org.joml.Matrix4f;import org.lwjgl.BufferUtils;import org.lwjgl.glfw.GLFW;import org.lwjgl.opengl.*;
public final class A10NapalmPreview {
 public static void main(String[] args)throws Exception{
  final int w=1280,h=720;GLFW.glfwInit();GLFW.glfwWindowHint(GLFW.GLFW_VISIBLE,GLFW.GLFW_FALSE);long win=GLFW.glfwCreateWindow(w,h,"hidden napalm preview",0,0);if(win==0)throw new AssertionError("context");GLFW.glfwMakeContextCurrent(win);GL.createCapabilities();Main.supported=true;
  int fbo=GL30.glGenFramebuffers();GL30.glBindFramebuffer(GL30.GL_FRAMEBUFFER,fbo);int[] slots=new int[4];
  for(int i=0;i<4;i++){int tex=GL11.glGenTextures();GL11.glBindTexture(GL11.GL_TEXTURE_2D,tex);GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,GL30.GL_RGBA16F,w,h,0,GL11.GL_RGBA,GL11.GL_FLOAT,(ByteBuffer)null);slots[i]=GL30.GL_COLOR_ATTACHMENT0+i;GL30.glFramebufferTexture2D(GL30.GL_FRAMEBUFFER,slots[i],GL11.GL_TEXTURE_2D,tex,0);}
  int depth=GL30.glGenRenderbuffers();GL30.glBindRenderbuffer(GL30.GL_RENDERBUFFER,depth);GL30.glRenderbufferStorage(GL30.GL_RENDERBUFFER,GL30.GL_DEPTH24_STENCIL8,w,h);GL30.glFramebufferRenderbuffer(GL30.GL_FRAMEBUFFER,GL30.GL_DEPTH_STENCIL_ATTACHMENT,GL30.GL_RENDERBUFFER,depth);GL20.glDrawBuffers(slots);if(GL30.glCheckFramebufferStatus(GL30.GL_FRAMEBUFFER)!=GL30.GL_FRAMEBUFFER_COMPLETE)throw new AssertionError("FBO");GL11.glViewport(0,0,w,h);
  FrameContext f=new FrameContext();f.scene=new SceneData();f.scene.daylightKnown=true;f.scene.daylightR=f.scene.daylightG=f.scene.daylightB=1;
  int index=0;
  for(double t:new double[]{5.5,5.9,6.3,6.7,7.1}){
   AircraftBridge.a10NapalmTick(t,0,0,0,0,40,60,1,1);Strafer.Pose p=AircraftBridge.strafer.pose();
   f.scene.originX=-p.x();f.scene.originY=0;f.scene.originZ=-p.y();
   if(index==0){f.eyeX=23;f.eyeY=(float)p.height()+4;f.eyeZ=28;f.scene.projection.identity().ortho(-16,16,-9,9,.1f,500);f.view=new Matrix4f().lookAt(f.eyeX,f.eyeY,f.eyeZ,0,(float)p.height()-1,0,0,1,0);}
   else{f.eyeX=110;f.eyeY=85;f.eyeZ=120;f.scene.projection.identity().ortho(-105,105,-59,59,.1f,600);f.view=new Matrix4f().lookAt(f.eyeX,f.eyeY,f.eyeZ,-25,25,0,0,1,0);}
   f.scene.projection.mul(f.view,f.viewProjection);GL11.glClearColor(0,0,0,0);GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT|GL11.GL_STENCIL_BUFFER_BIT);StraferRenderer.drawSafely(f);
   FloatBuffer rgb=BufferUtils.createFloatBuffer(w*h*4),norm=BufferUtils.createFloatBuffer(w*h*4);GL11.glReadBuffer(GL30.GL_COLOR_ATTACHMENT0);GL11.glReadPixels(0,0,w,h,GL11.GL_RGBA,GL11.GL_FLOAT,rgb);GL11.glReadBuffer(GL30.GL_COLOR_ATTACHMENT1);GL11.glReadPixels(0,0,w,h,GL11.GL_RGBA,GL11.GL_FLOAT,norm);
   BufferedImage im=new BufferedImage(w,h,BufferedImage.TYPE_INT_RGB);int pixels=0;
   for(int y=0;y<h;y++)for(int x=0;x<w;x++){
    int k=((h-1-y)*w+x)*4,col=0x1b242a;
    if(norm.get(k+3)>.5){pixels++;float shade=.42f+.58f*Math.max(0,norm.get(k)*.3f+norm.get(k+1)*.85f+norm.get(k+2)*.43f);col=0;for(int c=0;c<3;c++)col|=(int)(Math.min(1,Math.pow(Math.max(0,rgb.get(k+c)*shade),.7))*255)<<(16-8*c);}
    im.setRGB(x,y,col);
   }
   if(pixels<50)throw new AssertionError("empty A10 render");ImageIO.write(im,"png",Path.of(args[0],"napalm_preview_"+t+"s.png").toFile());index++;
  }
  if(GL11.glGetError()!=0)throw new AssertionError("GL state");System.out.println("A10 napalm 5 poses rendered; 4 G-buffer attachments; GL error 0");GLFW.glfwDestroyWindow(win);GLFW.glfwTerminate();
 }
}
