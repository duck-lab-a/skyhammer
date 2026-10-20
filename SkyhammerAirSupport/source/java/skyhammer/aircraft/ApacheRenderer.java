package skyhammer.aircraft;

import java.nio.*;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;

/**
 * Helicopter rendering, with independent Apache and UH-60 GPU resources and histories.
 * Flight and animation timing are shared; each airframe supplies its own rotor pivots.
 */
final class ApacheRenderer {
    private int program, vao, vbo, count;
    private int uMvp,uPlain,uPrevious,uModel,uPose,uPreviousPose,uLight,uEye;
    private boolean failed, announced;
    private final String meshName, shaderName;
    private static final class Craft {
        final String name;
        boolean history;
        long lastFrame;
        final float[] pose = new float[4], previousPose = new float[4];
        final Matrix4f previous = new Matrix4f();
        Craft(String name) { this.name = name; }
    }
    private static final Craft hellhound = new Craft("Apache"), ferryman = new Craft("Ferryman");
    private static final Matrix4f model = new Matrix4f(), mvp = new Matrix4f(), plain = new Matrix4f();
    private static final FloatBuffer matrix = BufferUtils.createFloatBuffer(16);
    private static final int[] oldBuffers = new int[4];
    private static final int[] buffers = {GL30.GL_COLOR_ATTACHMENT0,GL30.GL_COLOR_ATTACHMENT1,
        GL30.GL_COLOR_ATTACHMENT2,GL30.GL_COLOR_ATTACHMENT3};
    // rotor revolutions per second (chosen not to alias into a standstill at 60 fps)
    private static final double MAIN_REV = 4.3, TAIL_REV = 9.7;
    private ApacheRenderer(String meshName, String shaderName) { this.meshName=meshName; this.shaderName=shaderName; }
    private static final ApacheRenderer attack = new ApacheRenderer("apache.mesh","apache.vert");
    private static final ApacheRenderer transport = new ApacheRenderer("uh60.mesh","uh60.vert");

    static void drawSafely(FrameContext frame) {
        if (!Main.supported) return;
        long now = System.nanoTime();
        attack.drawCraft(frame, AircraftBridge.apache, hellhound, now);
        transport.drawCraft(frame, AircraftBridge.ferry, ferryman, now);
    }
    private void drawCraft(FrameContext frame, AircraftBridge.ApacheSample s, Craft c, long now) {
        if (failed) return;
        if (s == null || !s.pose().visible() || now-s.at() > 3_000_000_000L) { c.history=false; return; }
        try {
            draw(frame,s,c,now);
            if (!announced) { announced=true; System.out.println("[SkyhammerAircraft] "+c.name+" drawn; "+count/3+" triangles"); }
        } catch (Throwable e) {
            failed=true;
            AircraftBridge.fault=c.name+" "+e.getClass().getSimpleName()+": "+e.getMessage();
            System.err.println("[SkyhammerAircraft] Helicopter visual disabled: "+AircraftBridge.fault);
            e.printStackTrace();
        }
    }
    private void draw(FrameContext f, AircraftBridge.ApacheSample s, Craft c, long now) throws Exception {
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        int oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING);
        int oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        for(int i=0;i<4;i++) oldBuffers[i]=GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try {
            if (program==0) init();
            SceneData scene=f.scene;
            Hover.Pose p=s.pose();
            model.translation((float)(-p.x()-scene.originX), (float)(p.height()-scene.originY),
                    (float)(-p.y()-scene.originZ))
                .rotateY((float)p.yaw()).rotateX((float)p.pitch()).rotateZ((float)p.bank())
                .scale((float)s.scale());
            f.viewProjection.mul(model,mvp);
            scene.projection.mul(f.view,plain).mul(model);
            float[] pose=c.pose, previousPose=c.previousPose;
            pose[0]=(float)(Math.PI*2*((now*1e-9*MAIN_REV)%1));
            pose[1]=(float)(Math.PI*2*((now*1e-9*TAIL_REV)%1));
            pose[2]=(float)p.turretYaw(); pose[3]=(float)p.gunPitch();
            if (!c.history || now-c.lastFrame>250_000_000L) { c.previous.set(plain); System.arraycopy(pose,0,previousPose,0,4); }
            GL20.glUseProgram(program);
            upload(uMvp,mvp); upload(uPlain,plain); upload(uPrevious,c.previous); upload(uModel,model);
            GL20.glUniform4f(uPose,pose[0],pose[1],pose[2],pose[3]);
            GL20.glUniform4f(uPreviousPose,previousPose[0],previousPose[1],previousPose[2],previousPose[3]);
            GL20.glUniform3f(uLight,scene.daylightKnown?scene.daylightR:.6f,
                    scene.daylightKnown?scene.daylightG:.6f,scene.daylightKnown?scene.daylightB:.6f);
            GL20.glUniform3f(uEye,f.eyeX,f.eyeY,f.eyeZ);
            GL20.glDrawBuffers(buffers);
            GL11.glEnable(GL11.GL_DEPTH_TEST); GL11.glDepthFunc(GL11.GL_LEQUAL); GL11.glDepthMask(true);
            GL11.glDisable(GL11.GL_BLEND); GL11.glDisable(GL11.GL_CULL_FACE);
            GL11.glEnable(GL11.GL_STENCIL_TEST);
            GL11.glStencilMask(255); GL11.glStencilFunc(GL11.GL_ALWAYS,1,255);
            GL11.glStencilOp(GL11.GL_KEEP,GL11.GL_KEEP,GL11.GL_REPLACE);
            GL11.glDisable(GL11.GL_SCISSOR_TEST);
            GL11.glColorMask(true,true,true,true);
            GL30.glBindVertexArray(vao);
            GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);
            c.previous.set(plain); System.arraycopy(pose,0,previousPose,0,4); c.lastFrame=now; c.history=true;
        } finally {
            GL30.glBindVertexArray(oldVao); GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);
            GL20.glUseProgram(oldProgram);
            GL11.glPopAttrib();
            GL20.glDrawBuffers(oldBuffers);
        }
    }
    private static void upload(int location,Matrix4f value) {
        matrix.clear(); value.get(matrix); GL20.glUniformMatrix4fv(location,false,matrix);
    }
    private void init() throws Exception {
        try {
            program=AircraftRenderer.program(shaderName,"apache.frag");
            uMvp=uniform("uMvp"); uPlain=uniform("uPlain"); uPrevious=uniform("uPrevious");
            uModel=uniform("uModel"); uPose=uniform("uPose"); uPreviousPose=uniform("uPreviousPose");
            uLight=uniform("uLight"); uEye=uniform("uEye");
            FloatBuffer vertices=AircraftRenderer.mesh(meshName);
            count=vertices.remaining()/10;
            vao=GL30.glGenVertexArrays(); GL30.glBindVertexArray(vao);
            vbo=GL15.glGenBuffers(); GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
            GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);
            for(int i=0;i<4;i++) { GL20.glEnableVertexAttribArray(i); GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L); }
        } catch(Exception e) {
            if(vbo!=0)GL15.glDeleteBuffers(vbo); if(vao!=0)GL30.glDeleteVertexArrays(vao);
            if(program!=0)GL20.glDeleteProgram(program); program=vao=vbo=0; throw e;
        }
    }
    private int uniform(String name) { return GL20.glGetUniformLocation(program,name); }
}
