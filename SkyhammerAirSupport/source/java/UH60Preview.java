import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import org.lwjgl.*;
import org.lwjgl.glfw.*;
import org.lwjgl.opengl.*;
import org.joml.Matrix4f;

/** Renders the actual delivered mesh and animation shader in a hidden GL context. */
public class UH60Preview {
 static final int W=1440,H=1000;
 static int shader(int type,String s){int id=GL20.glCreateShader(type);GL20.glShaderSource(id,s);GL20.glCompileShader(id);if(GL20.glGetShaderi(id,GL20.GL_COMPILE_STATUS)==0)throw new RuntimeException(GL20.glGetShaderInfoLog(id));return id;}
 static int program(String v,String f){int p=GL20.glCreateProgram();GL20.glAttachShader(p,shader(GL20.GL_VERTEX_SHADER,v));GL20.glAttachShader(p,shader(GL20.GL_FRAGMENT_SHADER,f));GL20.glLinkProgram(p);if(GL20.glGetProgrami(p,GL20.GL_LINK_STATUS)==0)throw new RuntimeException(GL20.glGetProgramInfoLog(p));return p;}
 static void matrix(int p,String n,Matrix4f m){FloatBuffer b=BufferUtils.createFloatBuffer(16);m.get(b);GL20.glUniformMatrix4fv(GL20.glGetUniformLocation(p,n),false,b);}
 static void pose(int p,String n,float a,float b,float c,float d){GL20.glUniform4f(GL20.glGetUniformLocation(p,n),a,b,c,d);}
 static final String FRAG="""
 #version 330
 in vec3 vNormal,vColour,vPos;flat in float vPart;out vec4 frag;uniform vec3 eye;
 void main(){vec3 n=normalize(vNormal),v=normalize(eye-vPos);if(dot(n,v)<0.)n=-n;
 float key=max(0.,dot(n,normalize(vec3(-.6,1.,.7))));
 float fill=max(0.,dot(n,normalize(vec3(.8,.3,-.5))));
 float rim=pow(1.-max(dot(n,v),0.),3.);
 vec3 colour=vColour*(vec3(.48,.55,.62)+key*vec3(1.18,1.09,.88)+fill*.28)+rim*vec3(.05,.09,.12);
 if(vColour.b>vColour.r*1.5)colour+=pow(max(dot(reflect(-normalize(vec3(-.6,1.,.7)),n),v),0.),28.)*vec3(.48,.6,.65);
 frag=vec4(pow(clamp(colour,0.,1.),vec3(.4545)),1.);}
 """;
 static void png(Path p,byte[]rgb)throws Exception {BufferedImage im=new BufferedImage(W,H,BufferedImage.TYPE_INT_RGB);int[] row=new int[W];for(int y=0;y<H;y++){for(int x=0;x<W;x++){int i=(y*W+x)*3;row[x]=((rgb[i]&255)<<16)|((rgb[i+1]&255)<<8)|(rgb[i+2]&255);}im.setRGB(0,y,W,1,row,0,W);}ImageIO.write(im,"png",p.toFile());}
 public static void main(String[]args)throws Exception{
  Path root=Path.of(args[0]);boolean movie=args.length>1&&args[1].equals("movie");
  if(!GLFW.glfwInit())throw new RuntimeException("GLFW init");
  GLFW.glfwWindowHint(GLFW.GLFW_VISIBLE,GLFW.GLFW_FALSE);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MAJOR,3);GLFW.glfwWindowHint(GLFW.GLFW_CONTEXT_VERSION_MINOR,3);GLFW.glfwWindowHint(GLFW.GLFW_SAMPLES,4);
  long window=GLFW.glfwCreateWindow(W,H,"Apache mesh QA",0,0);if(window==0)throw new RuntimeException("GL context");GLFW.glfwMakeContextCurrent(window);GL.createCapabilities();
  System.err.println("GPU: "+GL11.glGetString(GL11.GL_RENDERER));
  String vs=Files.readString(root.resolve("skyhammer/aircraft/uh60.vert"));int p=program(vs,FRAG);
  // Compile and link the delivered four-attachment game shader too.
  int gameProgram=program(vs,Files.readString(root.resolve("skyhammer/aircraft/apache.frag")));GL20.glDeleteProgram(gameProgram);
  int count;float[]vertices;try(DataInputStream in=new DataInputStream(Files.newInputStream(root.resolve("skyhammer/aircraft/uh60.mesh")))){if(in.readInt()!=0x53484131)throw new RuntimeException("mesh magic");count=in.readInt();if(count<=0||count%3!=0||count>100000)throw new RuntimeException("vertex count");vertices=new float[count*10];for(int i=0;i<vertices.length;i++){vertices[i]=in.readFloat();if(!Float.isFinite(vertices[i]))throw new RuntimeException("nonfinite");}}
  int vao=GL30.glGenVertexArrays();GL30.glBindVertexArray(vao);int vbo=GL15.glGenBuffers();GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER,vbo);GL15.glBufferData(GL15.GL_ARRAY_BUFFER,vertices,GL15.GL_STATIC_DRAW);
  for(int i=0;i<4;i++){GL20.glEnableVertexAttribArray(i);GL20.glVertexAttribPointer(i,i==3?1:3,GL11.GL_FLOAT,false,40,i*12L);}
  GL11.glViewport(0,0,W,H);GL11.glPixelStorei(GL11.GL_PACK_ALIGNMENT,1);GL11.glEnable(GL13.GL_MULTISAMPLE);GL11.glEnable(GL11.GL_DEPTH_TEST);GL11.glDisable(GL11.GL_CULL_FACE);
  ByteBuffer pixels=BufferUtils.createByteBuffer(W*H*3);byte[] rgb=new byte[W*H*3];OutputStream out=new BufferedOutputStream(System.out,1<<20);
  float[][]cameras={{19,8,22},{-24,6,-16},{26,4,-3},{.1f,34,-3},{0,3,29}};String[]names={"uh60_preview_front3q.png","uh60_preview_rear3q.png","uh60_preview_side.png","uh60_preview_top.png","uh60_preview_front.png"};
  int frames=movie?240:cameras.length;
  for(int i=0;i<frames;i++){
   float t=i/30f;float[]eye=movie?new float[]{(float)Math.sin(.70+t*.24)*24,6+(float)Math.sin(t*.3), (float)Math.cos(.70+t*.24)*24}:cameras[i];
   GL11.glClearColor(.045f,.066f,.081f,1);GL11.glClear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT);GL20.glUseProgram(p);
   Matrix4f model=new Matrix4f();if(movie)model.translate(0,(float)Math.sin(t*1.3)*.11f,0).rotateZ((float)Math.sin(t*.8)*.025f);
   Matrix4f vp=new Matrix4f().perspective((float)Math.toRadians(40),(float)W/H,.1f,200).lookAt(eye[0],eye[1],eye[2],0,.7f,-1,0,1,0).mul(model);
   matrix(p,"uMvp",vp);matrix(p,"uPlain",vp);matrix(p,"uPrevious",vp);matrix(p,"uModel",model);
   float spin=movie?t*9:0;float yaw=movie?(float)Math.sin(t*.8)*.55f:0;float pitch=movie?.17f+(float)Math.sin(t*.7)*.10f:0;
   pose(p,"uPose",spin,-spin*1.7f,yaw,pitch);pose(p,"uPreviousPose",spin-.3f,-(spin-.3f)*1.7f,yaw,pitch);
   GL20.glUniform3f(GL20.glGetUniformLocation(p,"eye"),eye[0],eye[1],eye[2]);GL11.glDrawArrays(GL11.GL_TRIANGLES,0,count);
   pixels.clear();GL11.glReadPixels(0,0,W,H,GL11.GL_RGB,GL11.GL_UNSIGNED_BYTE,pixels);for(int row=0;row<H;row++){pixels.position((H-row-1)*W*3);pixels.get(rgb,row*W*3,W*3);}
   if(movie)out.write(rgb);else png(root.resolve(names[i]),rgb);
   int err=GL11.glGetError();if(err!=0)throw new RuntimeException("GL error "+err);
  }
  out.flush();GLFW.glfwDestroyWindow(window);GLFW.glfwTerminate();System.err.println("PASS: "+count/3+" triangles; both shader pairs link; "+frames+" frames without GL errors.");
 }
}
