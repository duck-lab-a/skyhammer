package skyhammer.aircraft;
public class DepartureAudioTest {
 static void ck(boolean x,String msg){if(!x)throw new AssertionError(msg);}
 public static void main(String[]a){
  int samples=0;
  for(int orbit:new int[]{180,377,799}){
   Flight f=new Flight();
   for(int i=0;i<orbit;i++)f.step(.05,2,2,100,100,0);
   ck(f.departureGain(100,100,0)==-1,"on-station sentinel");
   double prev=1,last=0;
   for(int i=0;i<241;i++){
    Flight.Pose p=f.step(.05,0,0,100,100,0);
    double g=f.departureGain(100,100,0);
    ck(Double.isFinite(g)&&g>=0&&g<=prev+1e-8,"smooth recession");
    if(i==0)ck(g>.98,"no departure cut");
    if(i==120)ck(g>.1,"audible after six seconds");
    if(i==238)ck(g<.001,"tail before disappearance");
    prev=g;last=g;samples++;
   }
   ck(last==0,"silent after hidden");
   f.step(.05,2,2,100,100,0);ck(f.departureGain(100,100,0)==-1,"recall normal ramp");
   f.reset();ck(f.departureGain(100,100,0)==0,"reset silent");
  }
  Flight f=new Flight();for(int i=0;i<400;i++)f.step(.05,2,2,100,100,0);
  for(int i=0;i<80;i++)f.step(.05,0,0,100,100,0);
  var p=f.pose();
  ck(f.departureGain(p.x(),p.y(),p.height())==1,"approaching listener bounded");
  ck(f.departureGain(500,500,0)<f.departureGain(100,100,0),"actual listener position");
  double before=f.departureGain(100,100,0);f.step(0,0,0,100,100,0);
  ck(f.departureGain(100,100,0)==before,"pause no envelope advance");
  AircraftBridge.reset();ck(Double.isNaN(AircraftBridge.ac130DepartureGain(100,100,0)),"missing sample fallback");
  for(int i=0;i<400;i++)AircraftBridge.tick(.05,2,2,100,100,0);
  AircraftBridge.tick(.05,0,0,100,100,0);
  ck(AircraftBridge.ac130DepartureGain(100,100,0)>.98,"bridge actual pose");
  var s=AircraftBridge.sample;
  AircraftBridge.sample=new AircraftBridge.Sample(s.pose(),System.nanoTime()-1_000_000_000L,s.scale(),s.flashUntil());
  ck(Double.isNaN(AircraftBridge.ac130DepartureGain(100,100,0)),"stale sample fallback");
  System.out.println("Departure audio passed: "+samples+" envelope samples plus pause/recall/listener/bridge cases");
 }
}
