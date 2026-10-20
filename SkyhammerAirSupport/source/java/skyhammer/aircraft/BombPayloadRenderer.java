package skyhammer.aircraft;

import java.nio.FloatBuffer;
import java.util.Arrays;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;

/** Existing canister mesh, one VBO, per-bomb G-buffer motion history. */
final class BombPayloadRenderer {
    static volatile boolean failed;
    private static int program,vao,vbo,count,uMvp,uPlain,uPrevious,uModel,uLight,uEye;
    private static boolean announced;
    private static final Matrix4f model=new Matrix4f(),clip=new Matrix4f(),plain=new Matrix4f(),pv=new Matrix4f();
    private static final Matrix4f[] previous=new Matrix4f[BombPayloads.MAX];
    private static final boolean[] visible=new boolean[BombPayloads.MAX];
    private static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
    private static final int[] oldBuffers=new int[4],buffers={GL30.GL_COLOR_ATTACHMENT0,GL30.GL_COLOR_ATTACHMENT1,GL30.GL_COLOR_ATTACHMENT2,GL30.GL_COLOR_ATTACHMENT3};
    private static long lastRun=Long.MIN_VALUE,lastFrame;
    private static double lastElapsed;
    private static double oldX,oldY,oldZ;
    private static boolean wasNuclear;
    static{for(int i=0;i<previous.length;i++)previous[i]=new Matrix4f();}
    private BombPayloadRenderer(){}
    static void drawSafely(FrameContext f){
        BombPayloads.Snapshot s=BombPayloads.current;
        if(failed||!Main.supported||s==null){Arrays.fill(visible,false);return;}
        try{draw(f,s);}
        catch(Throwable ex){failed=true;Arrays.fill(visible,false);System.err.println("[SkyhammerAircraft] Falling bomb visual disabled: "+ex);ex.printStackTrace();}
    }
    private static void draw(FrameContext f,BombPayloads.Snapshot s)throws Exception{
        long now=System.nanoTime();SceneData scene=f.scene;
        if(s.run()!=lastRun||now-lastFrame>250_000_000L||s.elapsed()<lastElapsed||s.elapsed()-lastElapsed>.5
                ||s.nuclear()!=wasNuclear||oldX!=scene.originX||oldY!=scene.originY||oldZ!=scene.originZ)Arrays.fill(visible,false);
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM),oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING),oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        for(int i=0;i<4;i++)oldBuffers[i]=GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try{
            if(program==0)init();GL20.glUseProgram(program);GL30.glBindVertexArray(vao);GL20.glDrawBuffers(buffers);
            GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(true);GL11.glDisable(GL11.GL_BLEND);GL11.glDisable(GL11.GL_CULL_FACE);
            GL11.glEnable(GL11.GL_STENCIL_TEST);GL11.glStencilMask(255);GL11.glStencilFunc(GL11.GL_ALWAYS,1,255);GL11.glStencilOp(GL11.GL_KEEP,GL11.GL_KEEP,GL11.GL_REPLACE);
            GL11.glDisable(GL11.GL_SCISSOR_TEST);GL11.glColorMask(true,true,true,true);
            GL20.glUniform3f(uLight,scene.daylightKnown?scene.daylightR:.6f,scene.daylightKnown?scene.daylightG:.6f,scene.daylightKnown?scene.daylightB:.6f);
            GL20.glUniform3f(uEye,f.eyeX,f.eyeY,f.eyeZ);scene.projection.mul(f.view,pv);
            int n=s.nuclear()?1:s.targets().length,drawn=0;
            for(int i=0;i<n;i++){
                BombFall.Pose p=BombPayloads.pose(s,i);if(!p.visible()){visible[i]=false;continue;}
                model.translation((float)(-p.x()-scene.originX),(float)(p.height()-scene.originY),(float)(-p.y()-scene.originZ)).rotateY((float)p.yaw()).rotateX((float)p.pitch()).scale((float)p.scale());
                pv.mul(model,plain);f.viewProjection.mul(model,clip);if(!visible[i])previous[i].set(plain);
                upload(uMvp,clip);upload(uPlain,plain);upload(uPrevious,previous[i]);upload(uModel,model);
                GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);previous[i].set(plain);visible[i]=true;drawn++;
            }
            for(int i=n;i<visible.length;i++)visible[i]=false;
            if(drawn>0&&!announced){announced=true;System.out.println("[SkyhammerAircraft] Falling bombs drawn; shared napalm mesh "+count/3+" triangles; scales 1.0 / 1.8");}
            lastFrame=now;lastRun=s.run();lastElapsed=s.elapsed();wasNuclear=s.nuclear();oldX=scene.originX;oldY=scene.originY;oldZ=scene.originZ;
        }finally{GL30.glBindVertexArray(oldVao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);GL20.glUseProgram(oldProgram);GL11.glPopAttrib();GL20.glDrawBuffers(oldBuffers);}
    }
    private static void upload(int u,Matrix4f m){matrix.clear();m.get(matrix);GL20.glUniformMatrix4fv(u,false,matrix);}
    private static int loc(String n){return GL20.glGetUniformLocation(program,n);}
    private static void init()throws Exception{
        try{
            program=AircraftRenderer.program("aircraft.vert","aircraft.frag");uMvp=loc("uMvp");uPlain=loc("uPlain");uPrevious=loc("uPrevious");uModel=loc("uModel");uLight=loc("uLight");uEye=loc("uEye");
            FloatBuffer data=AircraftRenderer.mesh("napalm.mesh");count=data.remaining()/10;
            vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferData(GL15.GL_ARRAY_BUFFER,data,GL15.GL_STATIC_DRAW);
            for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L);}
        }catch(Exception ex){if(vbo!=0)GL15.glDeleteBuffers(vbo);if(vao!=0)GL30.glDeleteVertexArrays(vao);if(program!=0)GL20.glDeleteProgram(program);program=vao=vbo=0;throw ex;}
    }
}
