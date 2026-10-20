import skyhammer.aircraft.*;
import java.nio.file.*;
public class NukeIntegrationTest {
 static void near(double a,double b,double eps){if(Math.abs(a-b)>eps)throw new AssertionError(a+" != "+b);}
 public static void main(String[] args)throws Exception{
  int cases=0;
  for(double heading:new double[]{0,.7,1.57,3.14})for(double alt:new double[]{30,60,150})for(double size:new double[]{.3,1,2}){
   for(int f=0;f<420;f++){
    double e=f/30.;Strafer.Pose n=Strafer.napalmPose(e,100,200,2,heading,40,alt),g=Strafer.pose(e,100,200,2,heading,40,alt);
    near(n.x(),g.x(),1e-8);near(n.y(),g.y(),1e-8);
    if(n.firing()||n.spin()!=0)throw new AssertionError("napalm gun suppression");
    if(e>=5&&e<=6.5&&(Math.toDegrees(n.pitch())<5||Math.toDegrees(n.pitch())>10))throw new AssertionError("napalm pitch");
    cases++;
   }
   for(int i=0;i<4;i++){
    double t=Strafer.releaseTime(i);near(t,5.6+i*.3,1e-10);
    Strafer.Canister before=Strafer.canister(t-1e-8,i,100,200,2,heading,40,alt,size),at=Strafer.canister(t,i,100,200,2,heading,40,alt,size);
    near(before.x(),at.x(),1e-5);near(before.y(),at.y(),1e-5);near(before.height(),at.height(),1e-5);
    Strafer.Canister end=Strafer.canister(t+.6-1e-8,i,100,200,2,heading,40,alt,size);
    near(end.x(),100+Math.cos(heading)*i*40/3.,1e-4);near(end.y(),200+Math.sin(heading)*i*40/3.,1e-4);near(end.height(),2*2.4494896,1e-4);
    if(Strafer.canister(t+.600001,i,100,200,2,heading,40,alt,size).visible())throw new AssertionError("landing expiry");cases++;
   }
  }
  AircraftBridge.nukeTick(30,100,200,0,1);if(AircraftBridge.nuke==null)throw new AssertionError("bridge");
  AircraftBridge.nukeTick(90,100,200,0,1);if(AircraftBridge.nuke!=null)throw new AssertionError("expiry");
  AircraftBridge.nukeTick(1,Double.NaN,0,0,1);if(AircraftBridge.nuke!=null)throw new AssertionError("nonfinite");
  AircraftBridge.nukeTick(1,0,0,0,5);near(AircraftBridge.nuke.size(),1.5,1e-10);
  AircraftBridge.reset();if(AircraftBridge.nuke!=null||AircraftBridge.strafer!=null)throw new AssertionError("reset");
  String result="{\"pass\":true,\"pose_and_drop_cases\":"+cases+",\"legacy_horizontal_path\":true,\"napalm_no_gun\":true,\"four_release_times\":[5.6,5.9,6.2,6.5],\"flight_seconds\":0.6,\"landing_fractions\":[0,0.3333333333333333,0.6666666666666666,1],\"bridge_range_and_reset\":true}";
  Files.writeString(Path.of(args[0]),result);System.out.println(result);
 }
}
