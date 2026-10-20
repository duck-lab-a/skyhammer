package skyhammer.aircraft;

import java.nio.*;
import java.awt.image.BufferedImage;
import java.io.InputStream;
import java.util.*;
import javax.imageio.ImageIO;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;
import viewpoint.render.Targets;

/** Sorted translucent HDR composite. Never blends opaque normals/depth/velocity. */
public final class NukeRenderer {
    private static FrameContext frame;
    private static Targets targets;
    private static long capturedAt;
    private static boolean libraryFrame,failed,announced;
    private static int program,vao,vbo,texture,count;
    private static final FloatBuffer vertices=BufferUtils.createFloatBuffer(640*6*10);
    private static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
    private static List<Nuke.Puff> cached;
    private static double cacheTime=-1,cacheSize;
    private static final float[][] QUAD={{-1,-1},{1,-1},{1,1},{-1,-1},{1,1},{-1,1}};
    private NukeRenderer(){}
    public static void capture(FrameContext f,Targets t){frame=f;targets=t;capturedAt=System.nanoTime();libraryFrame=false;}
    public static void allow(FrameContext f){if(f==frame)libraryFrame=true;}
    public static void drawSafely(SceneData scene){
        AircraftBridge.NukeSample s=AircraftBridge.nuke;
        if(failed||!Main.supported||!libraryFrame||frame==null||targets==null||frame.scene!=scene||
           s==null||System.nanoTime()-capturedAt>500_000_000L)return;
        try{
            draw(frame,s);
            if(!announced){announced=true;System.out.println("[SkyhammerAircraft] nuke drawn; "+count/3+" triangles");}
        }catch(Throwable e){failed=true;System.err.println("[SkyhammerAircraft] nuke visual disabled: "+e);e.printStackTrace();}
    }
    private static void mat(String n,Matrix4f value){matrix.clear();value.get(matrix);GL20.glUniformMatrix4fv(GL20.glGetUniformLocation(program,n),false,matrix);}
    private static void bind(int unit,int tex){GL13.glActiveTexture(GL13.GL_TEXTURE0+unit);GL11.glBindTexture(GL11.GL_TEXTURE_2D,tex);GL33.glBindSampler(unit,0);}
    private static void draw(FrameContext f,AircraftBridge.NukeSample s)throws Exception{
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM),oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING),oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);int[] textures=new int[2],samplers=new int[2];
        for(int i=0;i<2;i++){GL13.glActiveTexture(GL13.GL_TEXTURE0+i);textures[i]=GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);samplers[i]=GL30.glGetIntegeri(GL33.GL_SAMPLER_BINDING,i);}
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try{
            if(program==0)init();
            // Reuse samples while paused. At most 30 geometry evaluations per combat second.
            double t=Math.floor(s.elapsed()*30)/30.;
            if(cached==null||t!=cacheTime||s.size()!=cacheSize){cached=Nuke.sample(t,s.size());cacheTime=t;cacheSize=s.size();}
            Matrix4f v=f.view;
            cached.sort((a,b)->Float.compare(a.x()*v.m02()+a.y()*v.m12()+a.z()*v.m22(),b.x()*v.m02()+b.y()*v.m12()+b.z()*v.m22()));
            float cx=(float)(-s.x()-f.scene.originX),cy=(float)(s.z()*Projection.STOREY-f.scene.originY),cz=(float)(-s.y()-f.scene.originZ);
            vertices.clear();
            for(Nuke.Puff a:cached)for(float[] q:QUAD){
                float x=q[0]*a.rx(),y=q[1]*a.ry();
                vertices.put(cx+a.x()+v.m00()*x+v.m01()*y).put(cy+a.y()+v.m10()*x+v.m11()*y).put(cz+a.z()+v.m20()*x+v.m21()*y);
                vertices.put((a.tile()%4+(q[0]+1)*.5f)/4).put((a.tile()/4+(1-q[1])*.5f)/2);
                vertices.put(a.r()).put(a.g()).put(a.b()).put(a.alpha()).put(a.emissive());
            }
            vertices.flip();count=cached.size()*6;
            GL30.glBindVertexArray(vao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferSubData(GL15.GL_ARRAY_BUFFER,0,vertices);
            GL20.glUseProgram(program);mat("vp",f.viewProjection);mat("invFar",f.farInvPlainViewProjection);
            GL20.glUniform3f(GL20.glGetUniformLocation(program,"eye"),f.eyeX,f.eyeY,f.eyeZ);
            SceneData c=f.scene;
            GL20.glUniform3f(GL20.glGetUniformLocation(program,"light"),c.daylightKnown?c.daylightR:.6f,c.daylightKnown?c.daylightG:.6f,c.daylightKnown?c.daylightB:.6f);
            GL20.glUniform2f(GL20.glGetUniformLocation(program,"resolution"),f.width,f.height);
            GL20.glUniform1i(GL20.glGetUniformLocation(program,"hasFar"),targets.farDepth!=0&&f.farFar>f.farNear?1:0);
            bind(0,texture);bind(1,targets.farDepth);
            GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(false);
            GL11.glDisable(GL11.GL_CULL_FACE);GL11.glDisable(GL11.GL_STENCIL_TEST);GL11.glDisable(GL11.GL_SCISSOR_TEST);
            GL11.glColorMask(true,true,true,true);GL11.glEnable(GL11.GL_BLEND);
            GL14.glBlendEquation(GL14.GL_FUNC_ADD);GL14.glBlendFuncSeparate(GL11.GL_SRC_ALPHA,GL11.GL_ONE_MINUS_SRC_ALPHA,GL11.GL_ONE,GL11.GL_ONE_MINUS_SRC_ALPHA);
            GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);
        }finally{
            GL11.glPopAttrib();
            for(int i=0;i<2;i++){GL13.glActiveTexture(GL13.GL_TEXTURE0+i);GL11.glBindTexture(GL11.GL_TEXTURE_2D,textures[i]);GL33.glBindSampler(i,samplers[i]);}
            GL13.glActiveTexture(active);GL30.glBindVertexArray(oldVao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);GL20.glUseProgram(oldProgram);
        }
    }
    private static void init()throws Exception{
        program=AircraftRenderer.program("nuke.vert","nuke.frag");GL20.glUseProgram(program);
        GL20.glUniform1i(GL20.glGetUniformLocation(program,"atlas"),0);GL20.glUniform1i(GL20.glGetUniformLocation(program,"farDepth"),1);
        vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
        GL15.glBufferData(GL15.GL_ARRAY_BUFFER,640L*6*10*4,GL15.GL_STREAM_DRAW);
        int[] dims={3,2,4,1};int offset=0;for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,dims[i],GL11.GL_FLOAT,false,40,offset);offset+=dims[i]*4;}
        BufferedImage im;try(InputStream in=NukeRenderer.class.getResourceAsStream("nuke_smoke_atlas.png")){if(in==null)throw new java.io.FileNotFoundException("nuke_smoke_atlas.png");im=ImageIO.read(in);}
        ByteBuffer pixels=BufferUtils.createByteBuffer(im.getWidth()*im.getHeight()*4);
        for(int y=0;y<im.getHeight();y++)for(int x=0;x<im.getWidth();x++){int p=im.getRGB(x,y);pixels.put((byte)(p>>16)).put((byte)(p>>8)).put((byte)p).put((byte)(p>>24));}pixels.flip();
        texture=GL11.glGenTextures();bind(0,texture);GL11.glTexImage2D(GL11.GL_TEXTURE_2D,0,GL11.GL_RGBA8,im.getWidth(),im.getHeight(),0,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,pixels);
        GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_LINEAR);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_LINEAR);
        GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,GL12.GL_CLAMP_TO_EDGE);GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,GL12.GL_CLAMP_TO_EDGE);
    }
}
