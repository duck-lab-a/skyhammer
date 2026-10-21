package skyhammer.aircraft;

import java.io.*;
import java.nio.*;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;

/** One static vertex buffer, one draw; called on Viewpoint's render thread only. */
public final class AircraftRenderer {
    private static int program, vao, vbo, count;
    private static int uMvp,uPlain,uPrevious,uModel,uSpin,uPrevSpin,uFlash,uLight,uEye;
    private static boolean failed, announced, history;
    private static long lastFrame;
    private static float previousSpin;
    private static final Matrix4f model = new Matrix4f(), mvp = new Matrix4f(), plain = new Matrix4f();
    private static final Matrix4f previous = new Matrix4f();
    private static final FloatBuffer matrix = BufferUtils.createFloatBuffer(16);
    private static final int[] oldBuffers = new int[4];
    private static final int[] buffers = {GL30.GL_COLOR_ATTACHMENT0,GL30.GL_COLOR_ATTACHMENT1,
        GL30.GL_COLOR_ATTACHMENT2,GL30.GL_COLOR_ATTACHMENT3};
    private static boolean cameraFailed;
    private AircraftRenderer() {}
    /** Every frame Viewpoint draws: keep its camera for Lua, then draw the aircraft (AC-130, Apache). */
    public static void frame(FrameContext frame) {
        NukeRenderer.allow(frame);
        AngelFlareRenderer.allow(frame);
        if (Main.supported && !cameraFailed) {
            try { Projection.capture(frame); }
            catch (Throwable e) {
                cameraFailed = true;
                System.err.println("[SkyhammerAircraft] Camera capture disabled: " + e);
            }
        }
        drawSafely(frame);
        ApacheRenderer.drawSafely(frame);
        BomberRenderer.drawSafely(frame);
        BombPayloadRenderer.drawSafely(frame);
        StraferRenderer.drawSafely(frame);
    }
    public static void drawSafely(FrameContext frame) {
        if (failed || !Main.supported) return;
        AircraftBridge.Sample s = AircraftBridge.sample;
        long now = System.nanoTime();
        if (s == null || !s.pose().visible() || now-s.at() > 3_000_000_000L) { history=false; return; }
        try {
            draw(frame,s,now);
            if (!announced) { announced=true; System.out.println("[SkyhammerAircraft] G-buffer hook active; "+count/3+" triangles"); }
        } catch (Throwable e) {
            failed=true;
            AircraftBridge.fault=e.getClass().getSimpleName()+": "+e.getMessage();
            System.err.println("[SkyhammerAircraft] Visual disabled: "+AircraftBridge.fault);
            e.printStackTrace();
        }
    }
    private static void draw(FrameContext f, AircraftBridge.Sample s, long now) throws Exception {
        int oldProgram=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        int oldVao=GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING);
        int oldVbo=GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        for(int i=0;i<4;i++) oldBuffers[i]=GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try {
            if (program==0) init();
            SceneData scene=f.scene;
            Flight.Pose p=s.pose();
            model.translation((float)(-p.x()-scene.originX), (float)(p.height()-scene.originY),
                    (float)(-p.y()-scene.originZ))
                .rotateY((float)p.yaw()).rotateZ((float)p.bank()).scale((float)s.scale());
            f.viewProjection.mul(model,mvp);
            scene.projection.mul(f.view,plain).mul(model);
            float spin=(float)((now%10_000_000_000L)*1e-9*26);
            if (!history || now-lastFrame>250_000_000L) { previous.set(plain); previousSpin=spin; }
            GL20.glUseProgram(program);
            upload(uMvp,mvp); upload(uPlain,plain); upload(uPrevious,previous); upload(uModel,model);
            GL20.glUniform1f(uSpin,spin); GL20.glUniform1f(uPrevSpin,previousSpin);
            GL20.glUniform1f(uFlash,now<s.flashUntil()?1:0);
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
            previous.set(plain); previousSpin=spin; lastFrame=now; history=true;
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
    private static String text(String name) throws IOException {
        try(InputStream in=AircraftRenderer.class.getResourceAsStream("/skyhammer/aircraft/"+name)) {
            if(in==null)throw new FileNotFoundException(name);
            return new String(in.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
        }
    }
    private static int shader(int type,String source) {
        int id=GL20.glCreateShader(type);
        GL20.glShaderSource(id,source); GL20.glCompileShader(id);
        if(GL20.glGetShaderi(id,GL20.GL_COMPILE_STATUS)==0) {
            String error=GL20.glGetShaderInfoLog(id); GL20.glDeleteShader(id); throw new IllegalStateException(error);
        }
        return id;
    }
    /** A linked program from two shaders in this package. */
    static int program(String vert,String frag) throws IOException {
        int vs=0,fs=0,id=0;
        try {
            vs=shader(GL20.GL_VERTEX_SHADER,text(vert));
            fs=shader(GL20.GL_FRAGMENT_SHADER,text(frag));
            id=GL20.glCreateProgram(); GL20.glAttachShader(id,vs); GL20.glAttachShader(id,fs);
            GL20.glLinkProgram(id);
            if(GL20.glGetProgrami(id,GL20.GL_LINK_STATUS)==0)throw new IllegalStateException(GL20.glGetProgramInfoLog(id));
            return id;
        } catch(IOException|RuntimeException e) {
            if(id!=0)GL20.glDeleteProgram(id); throw e;
        } finally {
            if(vs!=0)GL20.glDeleteShader(vs); if(fs!=0)GL20.glDeleteShader(fs);
        }
    }
    /** A checked SHA1 mesh: 10 floats per vertex (position, normal, colour, part). */
    static FloatBuffer mesh(String name) throws IOException {
        InputStream raw=AircraftRenderer.class.getResourceAsStream("/skyhammer/aircraft/"+name);
        if(raw==null)throw new FileNotFoundException(name);
        try(DataInputStream in=new DataInputStream(new BufferedInputStream(raw))) {
            if(in.readInt()!=0x53484131) throw new IOException("Invalid SHA1 mesh header");
            int n=in.readInt(); if(n<=0||n>100_000||n%3!=0)throw new IOException("Invalid vertex count");
            FloatBuffer vertices=BufferUtils.createFloatBuffer(n*10);
            for(int i=0;i<n*10;i++) { float v=in.readFloat(); if(!Float.isFinite(v))throw new IOException("Nonfinite mesh");vertices.put(v); }
            return vertices.flip();
        }
    }
    private static void init() throws IOException {
        try {
            program=program("aircraft.vert","aircraft.frag");
            uMvp=uniform("uMvp"); uPlain=uniform("uPlain"); uPrevious=uniform("uPrevious");
            uModel=uniform("uModel"); uSpin=uniform("uSpin"); uPrevSpin=uniform("uPrevSpin");
            uFlash=uniform("uFlash"); uLight=uniform("uLight"); uEye=uniform("uEye");
            FloatBuffer vertices=mesh("ac130.mesh");
            count=vertices.remaining()/10;
            vao=GL30.glGenVertexArrays(); GL30.glBindVertexArray(vao);
            vbo=GL15.glGenBuffers(); GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
            GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);
            for(int i=0;i<4;i++) { GL20.glEnableVertexAttribArray(i); GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L); }
        } catch(IOException|RuntimeException e) {
            if(vbo!=0)GL15.glDeleteBuffers(vbo); if(vao!=0)GL30.glDeleteVertexArrays(vao);
            if(program!=0)GL20.glDeleteProgram(program); program=vao=vbo=0; throw e;
        }
    }
    private static int uniform(String name) { return GL20.glGetUniformLocation(program,name); }
}
