package skyhammer.aircraft;

import java.nio.FloatBuffer;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;

/** B-2 visual only; separate failure state and GL resources from the other aircraft. */
final class BomberRenderer {
    private static int program,vao,vbo,count,uMvp,uPlain,uPrevious,uModel,uLight,uEye,uVisibility;
    private static boolean failed,history,announced;
    private static long lastFrame,lastRun=Long.MIN_VALUE;
    private static final Matrix4f model=new Matrix4f(),mvp=new Matrix4f(),plain=new Matrix4f(),previous=new Matrix4f();
    private static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
    private static final int[] oldBuffers=new int[4];
    private static final int[] buffers={GL30.GL_COLOR_ATTACHMENT0,GL30.GL_COLOR_ATTACHMENT1,GL30.GL_COLOR_ATTACHMENT2,GL30.GL_COLOR_ATTACHMENT3};
    private BomberRenderer() {}
    static void drawSafely(FrameContext frame) {
        if(failed||!Main.supported)return;
        AircraftBridge.BomberSample s=AircraftBridge.bomber;
        long now=System.nanoTime();
        // The saved combat clock owns both plane and bombs. A wall-clock timeout
        // would hide only the plane after three seconds paused. Lua clears the run.
        if(s==null||!s.pose().visible()){history=false;return;}
        try {
            draw(frame,s,now);
            if(!announced){announced=true;System.out.println("[SkyhammerAircraft] B-2 drawn; "+count/3+" triangles");}
        } catch(Throwable e) {
            failed=true;
            System.err.println("[SkyhammerAircraft] B-2 visual disabled: "+e);
            e.printStackTrace();
        }
    }
    private static void draw(FrameContext f,AircraftBridge.BomberSample s,long now)throws Exception {
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        int oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING);
        int oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        for(int i=0;i<4;i++)oldBuffers[i]=GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try {
            if(program==0)init();
            SceneData scene=f.scene;Bomber.Pose p=s.pose();
            model.translation((float)(-p.x()-scene.originX),(float)(p.height()-scene.originY),(float)(-p.y()-scene.originZ))
                .rotateY((float)p.yaw()).scale((float)s.scale());
            f.viewProjection.mul(model,mvp);scene.projection.mul(f.view,plain).mul(model);
            if(!history||s.run()!=lastRun||now-lastFrame>250_000_000L)previous.set(plain);
            GL20.glUseProgram(program);GL20.glUniform1f(uVisibility,(float)BombPayloads.planeVisibility());
            upload(uMvp,mvp);upload(uPlain,plain);upload(uPrevious,previous);upload(uModel,model);
            GL20.glUniform3f(uLight,scene.daylightKnown?scene.daylightR:.6f,scene.daylightKnown?scene.daylightG:.6f,scene.daylightKnown?scene.daylightB:.6f);
            GL20.glUniform3f(uEye,f.eyeX,f.eyeY,f.eyeZ);
            GL20.glDrawBuffers(buffers);
            GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(true);
            GL11.glDisable(GL11.GL_BLEND);GL11.glDisable(GL11.GL_CULL_FACE);
            GL11.glEnable(GL11.GL_STENCIL_TEST);GL11.glStencilMask(255);
            GL11.glStencilFunc(GL11.GL_ALWAYS,1,255);GL11.glStencilOp(GL11.GL_KEEP,GL11.GL_KEEP,GL11.GL_REPLACE);
            GL11.glDisable(GL11.GL_SCISSOR_TEST);GL11.glColorMask(true,true,true,true);
            GL30.glBindVertexArray(vao);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);
            previous.set(plain);lastFrame=now;lastRun=s.run();history=true;
        } finally {
            GL30.glBindVertexArray(oldVao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);
            GL20.glUseProgram(oldProgram);GL11.glPopAttrib();GL20.glDrawBuffers(oldBuffers);
        }
    }
    private static void upload(int location,Matrix4f value){matrix.clear();value.get(matrix);GL20.glUniformMatrix4fv(location,false,matrix);}
    private static int uniform(String name){return GL20.glGetUniformLocation(program,name);}
    private static void init()throws Exception {
        try {
            // Every mesh part is zero: the shared aircraft shader makes no propeller motion.
            program=AircraftRenderer.program("aircraft.vert","bomber.frag");
            uMvp=uniform("uMvp");uPlain=uniform("uPlain");uPrevious=uniform("uPrevious");uModel=uniform("uModel");
            uLight=uniform("uLight");uEye=uniform("uEye");uVisibility=uniform("uVisibility");
            FloatBuffer vertices=AircraftRenderer.mesh("b2.mesh");count=vertices.remaining()/10;
            vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);
            vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);
            for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L);}
        }catch(Exception e){
            if(vbo!=0)GL15.glDeleteBuffers(vbo);if(vao!=0)GL30.glDeleteVertexArrays(vao);
            if(program!=0)GL20.glDeleteProgram(program);program=vao=vbo=0;throw e;
        }
    }
}
