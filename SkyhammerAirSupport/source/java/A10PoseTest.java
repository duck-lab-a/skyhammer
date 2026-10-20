package skyhammer.aircraft;
import skyhammer.aircraft.*;
import java.util.Locale;
import org.joml.Matrix4f; import org.joml.Vector3f;
public class A10PoseTest {
 static void check(boolean b,String s){if(!b)throw new AssertionError(s);}
 public static void main(String[] args){
  Locale.setDefault(Locale.ROOT);double max=0;int count=0;
  for(double alt:new double[]{30,60,150})for(int h=0;h<8;h++)for(int i=0;i<1400;i++){
   double e=i/100.,heading=h*Math.PI/4;Strafer.Pose p=Strafer.pose(e,1000,2000,3,heading,30,alt);
   check(p.visible(),"visible");double d=(e-7.6)*50;
   check(Math.abs(p.x()-(1000+Math.cos(heading)*d))<1e-8&&Math.abs(p.y()-(2000+Math.sin(heading)*d))<1e-8,"horizontal contract");
   check(Double.isFinite(p.pitch()+p.bank()+p.height()),"finite pose");
   if(e>=5&&e<=6.5){
    double t=Strafer.targetAlong(e,30);Vector3f actual=new Matrix4f().rotateY((float)p.yaw()).rotateX((float)p.pitch()).rotateZ((float)p.bank()).transformDirection(new Vector3f(0,0,1));
    double ax=-actual.x,ay=-actual.z,az=actual.y;
    double tx=1000+Math.cos(heading)*t-p.x(),ty=2000+Math.sin(heading)*t-p.y(),tz=3*Projection.STOREY-p.height();
    double dot=(ax*tx+ay*ty+az*tz)/Math.sqrt((ax*ax+ay*ay+az*az)*(tx*tx+ty*ty+tz*tz));
    double error=Math.toDegrees(Math.acos(Math.max(-1,Math.min(1,dot))));max=Math.max(max,error);check(error<.001,"aim "+error);count++;
   }
  }
  for(double e:new double[]{-1,14,20,Double.NaN})check(!Strafer.pose(e,0,0,0,0,30,60).visible(),"hidden boundaries");
  check(!Strafer.pose(5,0,0,0,0,0,60).visible(),"invalid length");
  AircraftBridge.a10Tick(6,0,0,0,0,30,60,9,1);check(AircraftBridge.strafer.scale()==2,"size clamp");
  AircraftBridge.a10Clear();check(AircraftBridge.strafer==null,"clear");
  AircraftBridge.a10Tick(6,0,0,0,0,30,60,1,1);AircraftBridge.reset();check(AircraftBridge.strafer==null,"global reset");
  System.out.printf("{\"pass\":true,\"samples\":33600,\"aim_samples\":%d,\"max_aim_error_degrees\":%.9f,\"rows\":[",count,max);
  boolean comma=false;
  for(double e:new double[]{0,5,6,6.5,7.6,10,13.9}){
   Strafer.Pose p=Strafer.pose(e,0,0,0,0,30,60);
   if(comma)System.out.print(",");comma=true;
   System.out.printf("{\"e\":%.2f,\"x\":%.6f,\"y\":%.6f,\"height\":%.6f,\"pitch_degrees\":%.6f,\"bank_degrees\":%.6f,\"firing\":%s}",e,p.x(),p.y(),p.height(),Math.toDegrees(p.pitch()),Math.toDegrees(p.bank()),p.firing());
  }
  System.out.println("]}");
 }
}

