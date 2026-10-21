package skyhammer.aircraft;

import java.nio.FloatBuffer;
import java.nio.IntBuffer;
import org.joml.Matrix4f;
import org.lwjgl.BufferUtils;
import org.lwjgl.opengl.*;
import org.lwjgl.system.MemoryUtil;
import viewpoint.render.FrameContext;
import viewpoint.render.SceneData;
import viewpoint.render.Targets;

/** Two bounded HDR draws: sorted alpha smoke, then additive hot cores. No frame allocations. */
public final class AngelFlareRenderer {
    private static final int MAX_SMOKE=AngelFlares.MAX_FLARES*(AngelFlares.MAX_SEGMENTS-4);
    private static final int MAX_QUADS=AngelFlares.MAX_FLARES*(AngelFlares.MAX_SEGMENTS+1);
    private static final FloatBuffer vertices=BufferUtils.createFloatBuffer(MAX_QUADS*6*9);
    private static final FloatBuffer matrix=BufferUtils.createFloatBuffer(16);
    private static final IntBuffer state=BufferUtils.createIntBuffer(1);
    // Cache direct addresses: Java 25's LWJGL FFM memAddress(Buffer) can allocate a
    // NativeMemorySegment wrapper until the JVM escape analysis has warmed up.
    private static final long VERTEX_ADDRESS=MemoryUtil.memAddress(vertices);
    private static final long MATRIX_ADDRESS=MemoryUtil.memAddress(matrix);
    private static final long STATE_ADDRESS=MemoryUtil.memAddress(state);
    // World-space segment endpoints, width/alpha; fixed arrays shared by all frames.
    private static final double[] ax=new double[MAX_SMOKE],ay=new double[MAX_SMOKE],az=new double[MAX_SMOKE],
        bx=new double[MAX_SMOKE],by=new double[MAX_SMOKE],bz=new double[MAX_SMOKE];
    private static final float[] widths=new float[MAX_SMOKE],alphas=new float[MAX_SMOKE],depths=new float[MAX_SMOKE];
    private static final int[] order=new int[MAX_SMOKE];
    private static final double[] p0=new double[3],p1=new double[3];
    private static final int[] CORNER={0,1,2,0,2,3};
    private static FrameContext frame;
    private static Targets targets;
    private static boolean allowed,failed;
    private static int program,vao,vbo,uVP,uFar,uEye,uLight,uRes,uHasFar,uCore;
    private static int smokeVertices,coreVertices;
    private AngelFlareRenderer(){}
    public static void capture(FrameContext f,Targets t){frame=f;targets=t;allowed=false;}
    public static void allow(FrameContext f){if(frame==f)allowed=true;}
    public static void drawSafely(SceneData scene){
        // No GL queries, geometry processing or locking while no decoys exist.
        if(!AircraftBridge.flares.active||failed||!Main.supported||!allowed||frame==null||targets==null||frame.scene!=scene)return;
        try{draw(frame);}catch(Throwable e){
            failed=true;System.err.println("[SkyhammerAircraft] flare visual disabled: "+e);
        }
    }
    private static void mat(int u,Matrix4f m){matrix.clear();m.get(matrix);GL20.nglUniformMatrix4fv(u,1,false,MATRIX_ADDRESS);}
    // LWJGL's scalar glGetInteger convenience overload creates temporary buffer wrappers.
    private static int integer(int name){GL11.nglGetIntegerv(name,STATE_ADDRESS);return state.get(0);}
    private static void build(FrameContext f){
        vertices.clear();int n=0;
        AngelFlares a=AircraftBridge.flares;
        synchronized(a){
            for(int i=0;i<AngelFlares.MAX_FLARES;i++){
                double age=a.time-a.born[i];
                if(age<=0||age>=AngelFlares.BURN+AngelFlares.TRAIL_LIFE)continue;
                double end=Math.min(age,AngelFlares.BURN),step=AngelFlares.BURN/(a.segments-4);
                for(int j=0;j<a.segments-4;j++){
                    double t0=j*step,t1=Math.min(end,(j+1)*step);
                    if(t0>=end)break;
                    double smokeAge=age-(t0+t1)*.5;
                    float alpha=(float)(.34*Math.exp(-.35*smokeAge)*AngelFlares.fade(smokeAge));
                    if(alpha<.003)continue;
                    a.position(i,t0,p0);a.position(i,t1,p1);
                    // A slow common drift, not falling ballistic smoke.
                    double wind=smokeAge*.20,rise=smokeAge*.15;
                    // Visual wake roll-up only: the smoke rises behind the aircraft,
                    // while burning tips keep their independent ballistic paths.
                    double rollSide=0;
                    if(!a.central[i]){double turn=Math.min(2.4,smokeAge*.9),weight=Math.exp(-(t0+t1)*.35);
                        rise+=(10*Math.sin(turn)+3*(1-Math.exp(-smokeAge)))*weight;
                        rollSide=10*(1-Math.cos(turn))*weight;}
                    double curl=smokeAge*.3;
                    double dx=Math.sin(i*1.17+j*.73+smokeAge*.4)*curl+a.sideX[i]*rollSide;
                    double dy=Math.cos(i*.67+j*.55+smokeAge*.3)*curl*.6;
                    double dz=Math.sin(i*.57+j*.49+smokeAge*.35)*curl+a.sideZ[i]*rollSide;
                    ax[n]=p0[0]+wind+dx;ay[n]=p0[1]+rise+dy;az[n]=p0[2]+dz;
                    bx[n]=p1[0]+wind+dx;by[n]=p1[1]+rise+dy;bz[n]=p1[2]+dz;
                    double length=Math.sqrt(Math.pow(p1[0]-p0[0],2)+Math.pow(p1[1]-p0[1],2)+Math.pow(p1[2]-p0[2],2));
                    widths[n]=(float)((.55+.40*smokeAge+length*.7)*(1+.22*Math.sin(i*2.1+j*1.7)));
                    alphas[n]=alpha;
                    double mx=(ax[n]+bx[n])*.5-f.scene.originX,my=(ay[n]+by[n])*.5-f.scene.originY,mz=(az[n]+bz[n])*.5-f.scene.originZ;
                    depths[n]=(float)(mx*f.view.m02()+my*f.view.m12()+mz*f.view.m22());
                    order[n]=n;n++;
                }
            }
            // Bounded in-place Shell sort. No boxed keys, comparator, lists or streams.
            for(int gap=n/2;gap>0;gap/=2)for(int i=gap;i<n;i++){
                int id=order[i],j=i;
                while(j>=gap&&depths[order[j-gap]]>depths[id]){order[j]=order[j-gap];j-=gap;}
                order[j]=id;
            }
            for(int k=0;k<n;k++)ribbon(f,order[k]);
            smokeVertices=vertices.position()/9;
            for(int i=0;i<AngelFlares.MAX_FLARES;i++){
                double age=a.time-a.born[i];
                if(age<0||age>=AngelFlares.BURN)continue;
                float fade=(float)Math.min(1,(AngelFlares.BURN-age)/.4);
                // Four short luminous segments replace four smoke samples.
                // Total budget remains 928 quads, with the same two draw calls.
                double tailStart=Math.max(0,age-(a.central[i]?age:.9));
                for(int j=0;j<4;j++){
                    double t0=tailStart+(age-tailStart)*j/4;
                    double t1=tailStart+(age-tailStart)*(j+1)/4;
                    a.position(i,t0,p0);a.position(i,t1,p1);
                    streak(f,p0,p1,(a.central[i]?.45:.50),fade*(a.central[i]?.95f:(.035f+.065f*j*j)));
                }
                a.position(i,age,p0);
                core(f,p0[0]-f.scene.originX,p0[1]-f.scene.originY,p0[2]-f.scene.originZ,fade);
            }
        }
        coreVertices=vertices.position()/9-smokeVertices;vertices.flip();
    }
    private static void vertex(double x,double y,double z,float u,float v,float r,float g,float b,float alpha){
        vertices.put((float)x).put((float)y).put((float)z).put(u).put(v).put(r).put(g).put(b).put(alpha);
    }
    private static void ribbon(FrameContext f,int i){
        double x=(ax[i]+bx[i])*.5-f.scene.originX;
        double y=(ay[i]+by[i])*.5-f.scene.originY;
        double z=(az[i]+bz[i])*.5-f.scene.originZ;
        double angle=i*2.39996,c=Math.cos(angle),s=Math.sin(angle),size=widths[i];
        for(int corner:CORNER){
            double u=corner==1||corner==2?1:-1,v=corner>=2?1:-1;
            double rx=(u*c-v*s)*size,ry=(u*s+v*c)*size;
            vertex(x+f.view.m00()*rx+f.view.m01()*ry,
                y+f.view.m10()*rx+f.view.m11()*ry,
                z+f.view.m20()*rx+f.view.m21()*ry,
                (float)(u*.5+.5),(float)(v*.5+.5),.96f,.97f,1,alphas[i]);
        }
    }
    private static void streak(FrameContext f,double[] a,double[] b,double width,float alpha){
        double dx=b[0]-a[0],dy=b[1]-a[1],dz=b[2]-a[2];
        // Frame eye is relative to the floating origin; the analytic endpoints
        // are absolute world coordinates. Keep the cross-product in one space.
        double ex=f.eyeX+f.scene.originX-(a[0]+b[0])*.5;
        double ey=f.eyeY+f.scene.originY-(a[1]+b[1])*.5;
        double ez=f.eyeZ+f.scene.originZ-(a[2]+b[2])*.5;
        double sx=dy*ez-dz*ey,sy=dz*ex-dx*ez,sz=dx*ey-dy*ex;
        double inv=width/Math.max(.000001,Math.sqrt(sx*sx+sy*sy+sz*sz));
        sx*=inv;sy*=inv;sz*=inv;
        for(int c:CORNER){
            boolean end=c>=2;double sign=c==1||c==2?1:-1;
            double[] p=end?b:a;
            vertex(p[0]+sign*sx-f.scene.originX,p[1]+sign*sy-f.scene.originY,p[2]+sign*sz-f.scene.originZ,
                sign>0?1:0,end?1:0,1,.75f,.32f,-alpha);
        }
    }
    private static void core(FrameContext f,double x,double y,double z,float alpha){
        double size=1.6;
        for(int c:CORNER){
            double u=c==1||c==2?1:-1,v=c>=2?1:-1;
            vertex(x+size*(f.view.m00()*u+f.view.m01()*v),y+size*(f.view.m10()*u+f.view.m11()*v),
                z+size*(f.view.m20()*u+f.view.m21()*v),(float)(u*.5+.5),(float)(v*.5+.5),1,.85f,.46f,alpha);
        }
    }
    private static void draw(FrameContext f)throws Exception{
        build(f);
        if(vertices.remaining()==0)return;
        int oldProgram=integer(GL20.GL_CURRENT_PROGRAM),oldVao=integer(GL30.GL_VERTEX_ARRAY_BINDING),oldVbo=integer(GL15.GL_ARRAY_BUFFER_BINDING);
        int active=integer(GL13.GL_ACTIVE_TEXTURE);
        GL13.glActiveTexture(GL13.GL_TEXTURE0);
        int texture=integer(GL11.GL_TEXTURE_BINDING_2D);
        GL30.nglGetIntegeri_v(GL33.GL_SAMPLER_BINDING,0,STATE_ADDRESS);int sampler=state.get(0);
        GL11.glPushAttrib(GL11.GL_ALL_ATTRIB_BITS);
        try{
            if(program==0)init();
            GL20.glUseProgram(program);
            GL30.glBindVertexArray(vao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
            GL15.nglBufferSubData(GL15.GL_ARRAY_BUFFER,0,vertices.remaining()*4L,VERTEX_ADDRESS);
            mat(uVP,f.viewProjection);mat(uFar,f.farInvPlainViewProjection);
            GL20.glUniform3f(uEye,f.eyeX,f.eyeY,f.eyeZ);
            SceneData s=f.scene;
            GL20.glUniform3f(uLight,s.daylightKnown?s.daylightR:.6f,s.daylightKnown?s.daylightG:.6f,s.daylightKnown?s.daylightB:.6f);
            GL20.glUniform2f(uRes,f.width,f.height);
            GL20.glUniform1i(uHasFar,targets.farDepth!=0&&f.farFar>f.farNear?1:0);
            GL11.glBindTexture(GL11.GL_TEXTURE_2D,targets.farDepth);GL33.glBindSampler(0,0);
            GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDepthFunc(GL11.GL_LEQUAL);GL11.glDepthMask(false);
            GL11.glDisable(GL11.GL_CULL_FACE);GL11.glDisable(GL11.GL_STENCIL_TEST);GL11.glDisable(GL11.GL_SCISSOR_TEST);
            GL11.glColorMask(true,true,true,true);GL11.glEnable(GL11.GL_BLEND);GL14.glBlendEquation(GL14.GL_FUNC_ADD);
            GL14.glBlendFuncSeparate(GL11.GL_SRC_ALPHA,GL11.GL_ONE_MINUS_SRC_ALPHA,GL11.GL_ONE,GL11.GL_ONE_MINUS_SRC_ALPHA);
            GL20.glUniform1i(uCore,0);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,smokeVertices);
            GL14.glBlendFuncSeparate(GL11.GL_SRC_ALPHA,GL11.GL_ONE,GL11.GL_ZERO,GL11.GL_ONE);
            GL20.glUniform1i(uCore,1);GL11.glDrawArrays(GL11.GL_TRIANGLES,smokeVertices,coreVertices);
        }finally{
            GL11.glPopAttrib();
            GL11.glBindTexture(GL11.GL_TEXTURE_2D,texture);GL33.glBindSampler(0,sampler);GL13.glActiveTexture(active);
            GL30.glBindVertexArray(oldVao);GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,oldVbo);GL20.glUseProgram(oldProgram);
        }
    }
    private static void init()throws Exception{
        program=AircraftRenderer.program("angel.vert","angel.frag");GL20.glUseProgram(program);
        uVP=uniform("vp");uFar=uniform("invFar");uEye=uniform("eye");uLight=uniform("light");
        uRes=uniform("resolution");uHasFar=uniform("hasFar");uCore=uniform("core");
        GL20.glUniform1i(uniform("farDepth"),0);
        vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);
        GL15.glBufferData(GL15.GL_ARRAY_BUFFER,MAX_QUADS*6L*9*4,GL15.GL_STREAM_DRAW);
        GL20.glEnableVertexAttribArray(0);GL20.glVertexAttribPointer(0,3,GL11.GL_FLOAT,false,36,0);
        GL20.glEnableVertexAttribArray(1);GL20.glVertexAttribPointer(1,2,GL11.GL_FLOAT,false,36,12);
        GL20.glEnableVertexAttribArray(2);GL20.glVertexAttribPointer(2,4,GL11.GL_FLOAT,false,36,20);
    }
    private static int uniform(String name){return GL20.glGetUniformLocation(program,name);}
}
