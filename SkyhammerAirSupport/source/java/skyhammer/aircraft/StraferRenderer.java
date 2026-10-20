package skyhammer.aircraft;

import java.nio.FloatBuffer;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;

/** A-10 visual only; separate failure state and GL resources from the other aircraft. */
final class StraferRenderer {
    private static int program,vao,vbo,count,uMvp,uPlain,uPrevious,uModel,uLight,uEye,uSpin,uPrevSpin,uBarrelAxis,uFlash;
    private static float previousSpin;
    private static double previousElapsed;
    private static int airframeCount;
    private static boolean failed,history,announced;
    private static long lastFrame,lastRun=Long.MIN_VALUE;
    private static final Matrix4f model=new Matrix4f(),mvp=new Matrix4f(),plain=new Matrix4f(),previous=new Matrix4f();
    private static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
    private static final int[] oldBuffers=new int[4];
    private static final int[] buffers={GL30.GL_COLOR_ATTACHMENT0,GL30.GL_COLOR_ATTACHMENT1,GL30.GL_COLOR_ATTACHMENT2,GL30.GL_COLOR_ATTACHMENT3};
    private StraferRenderer() {}
    static void drawSafely(FrameContext frame) {
        if(failed||!Main.supported)return;
        AircraftBridge.StraferSample s=AircraftBridge.strafer;
        long now=System.nanoTime();
        if(s==null||!s.pose().visible()||now-s.at()>3_000_000_000L){history=false;return;}
        try {
            draw(frame,s,now);
            if(!announced){announced=true;System.out.println("[SkyhammerAircraft] A-10 drawn; "+airframeCount/3+" triangles");}
        } catch(Throwable e) {
            failed=true;
            System.err.println("[SkyhammerAircraft] A-10 visual disabled: "+e);
            e.printStackTrace();
        }
    }
    private static void draw(FrameContext f,AircraftBridge.StraferSample s,long now)throws Exception {
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        int oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING);
        int oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        for(int i=0;i<4;i++)oldBuffers[i]=GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try {
            if(program==0)init();
            SceneData scene=f.scene;Strafer.Pose p=s.pose();
            model.translation((float)(-p.x()-scene.originX),(float)(p.height()-scene.originY),(float)(-p.y()-scene.originZ))
                .rotateY((float)p.yaw()).rotateX((float)p.pitch()).rotateZ((float)p.bank()).scale((float)s.scale());
            f.viewProjection.mul(model,mvp);scene.projection.mul(f.view,plain).mul(model);
            float spin=(float)p.spin();
            if(!history||s.run()!=lastRun||now-lastFrame>250_000_000L||p.elapsed()<previousElapsed||p.elapsed()-previousElapsed>.5){previous.set(plain);previousSpin=spin;}
            GL20.glUseProgram(program);
            upload(uMvp,mvp);upload(uPlain,plain);upload(uPrevious,previous);upload(uModel,model);
            GL20.glUniform1f(uSpin,spin);GL20.glUniform1f(uPrevSpin,previousSpin);
            GL20.glUniform3f(uBarrelAxis,(float)Strafer.GUN_X,(float)Strafer.GUN_Y,(float)Strafer.GUN_Z);
            GL20.glUniform1f(uFlash,p.firing()?1:0);
            GL20.glUniform3f(uLight,scene.daylightKnown?scene.daylightR:.6f,scene.daylightKnown?scene.daylightG:.6f,scene.daylightKnown?scene.daylightB:.6f);
            GL20.glUniform3f(uEye,f.eyeX,f.eyeY,f.eyeZ);
            GL20.glDrawBuffers(buffers);
            GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(true);
            GL11.glDisable(GL11.GL_BLEND);GL11.glDisable(GL11.GL_CULL_FACE);
            GL11.glEnable(GL11.GL_STENCIL_TEST);GL11.glStencilMask(255);
            GL11.glStencilFunc(GL11.GL_ALWAYS,1,255);GL11.glStencilOp(GL11.GL_KEEP,GL11.GL_KEEP,GL11.GL_REPLACE);
            GL11.glDisable(GL11.GL_SCISSOR_TEST);GL11.glColorMask(true,true,true,true);
            GL30.glBindVertexArray(vao);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);
            // Napalm flight bodies intentionally hidden; Lua still owns all ground effects.
            previous.set(plain);previousSpin=spin;previousElapsed=p.elapsed();lastFrame=now;lastRun=s.run();history=true;
        } finally {
            GL30.glBindVertexArray(oldVao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);
            GL20.glUseProgram(oldProgram);GL11.glPopAttrib();GL20.glDrawBuffers(oldBuffers);
        }
    }
    private static void upload(int location,Matrix4f value){matrix.clear();value.get(matrix);GL20.glUniformMatrix4fv(location,false,matrix);}
    private static int uniform(String name){return GL20.glGetUniformLocation(program,name);}
    private static void flash(FloatBuffer out,float[] a,float[] b,float[] c){
        org.joml.Vector3f n=new org.joml.Vector3f(b).sub(new org.joml.Vector3f(a))
            .cross(new org.joml.Vector3f(c).sub(new org.joml.Vector3f(a))).normalize();
        for(float[] p:new float[][]{a,b,c})out.put(p).put(n.x).put(n.y).put(n.z).put(1f).put(.72f).put(.22f).put(5f);
    }
    private static void init()throws Exception {
        try {
            // Only part 1 rotates; its axis is supplied by a uniform. Part 5 is render-only muzzle flash.
            program=AircraftRenderer.program("a10.vert","aircraft.frag");
            uMvp=uniform("uMvp");uPlain=uniform("uPlain");uPrevious=uniform("uPrevious");uModel=uniform("uModel");
            uSpin=uniform("uSpin");uPrevSpin=uniform("uPrevSpin");uBarrelAxis=uniform("uBarrelAxis");uFlash=uniform("uFlash");
            uLight=uniform("uLight");uEye=uniform("uEye");
            FloatBuffer mesh=AircraftRenderer.mesh("a10.mesh");airframeCount=mesh.remaining()/10;
            // A small closed, pointed flash, sharing the existing fragment/G-buffer contract.
            int sides=8;FloatBuffer vertices=BufferUtils.createFloatBuffer(mesh.remaining()+sides*6*10);
            vertices.put(mesh);
            for(int i=0;i<sides;i++){
                double a=2*Math.PI*i/sides,b=2*Math.PI*(i+1)/sides;
                float x=(float)Strafer.GUN_X,y=(float)Strafer.GUN_Y;
                float[] p0={x,y,8.16f},p1={x+.28f*(float)Math.cos(a),y+.28f*(float)Math.sin(a),8.5f};
                float[] p2={x+.28f*(float)Math.cos(b),y+.28f*(float)Math.sin(b),8.5f},tip={x,y,9.6f};
                flash(vertices,p0,p1,p2);flash(vertices,tip,p2,p1);
            }
            vertices.flip();count=vertices.remaining()/10;
            vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);
            vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);
            for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L);}
        }catch(Exception e){
            if(vbo!=0)GL15.glDeleteBuffers(vbo);if(vao!=0)GL30.glDeleteVertexArrays(vao);
            if(program!=0)GL20.glDeleteProgram(program);program=vao=vbo=0;throw e;
        }
    }
}
