import skyhammer.aircraft.Nuke;
import java.nio.file.*;
import java.util.*;
public final class NukeGeometryTest {
 public static void main(String[] args)throws Exception{
  int maximum=0,samples=0;double minAlpha=1,maxAlpha=0;StringBuilder bounds=new StringBuilder();
  for(double scale:new double[]{.5,1,1.5})for(int frame=0;frame<=2700;frame++){
   List<Nuke.Puff> p=Nuke.sample(frame/30.,scale);maximum=Math.max(maximum,p.size()*2);samples++;
   for(Nuke.Puff a:p){
    if(!Float.isFinite(a.x()+a.y()+a.z()+a.rx()+a.ry()+a.alpha()))throw new AssertionError("finite");
    if(a.alpha()<0||a.alpha()>1||a.rx()<=0||a.ry()<=0||a.tile()<0||a.tile()>7)throw new AssertionError("particle range");
    minAlpha=Math.min(minAlpha,a.alpha());maxAlpha=Math.max(maxAlpha,a.alpha());
   }
  }
  for(double e:new double[]{8,30,60}){
   List<Nuke.Puff> p=Nuke.sample(e,1);double height=0,left=1e9,right=-1e9;
   for(Nuke.Puff a:p){height=Math.max(height,a.y()+a.ry());if(a.y()>200){left=Math.min(left,a.x()-a.rx());right=Math.max(right,a.x()+a.rx());}}
   if(height<250||height>350)throw new AssertionError("crown height "+height);
   if(bounds.length()>0)bounds.append(",");bounds.append(String.format(Locale.ROOT,"{\"time\":%.1f,\"quad_bound_height_m\":%.3f,\"quad_bound_cap_width_m\":%.3f}",e,height,right-left));
  }
  if(!Nuke.sample(90,1).isEmpty()||!Nuke.sample(-1,1).isEmpty()||!Nuke.sample(Double.NaN,1).isEmpty())throw new AssertionError("lifetime");
  // Deterministic sampling is essential for pause/resume and save reload.
  if(!Nuke.sample(17.25,1).equals(Nuke.sample(17.25,1)))throw new AssertionError("determinism");
  String result="{\"pass\":true,\"sample_count\":"+samples+",\"max_triangles_all_frames\":"+maximum+",\"alpha_min\":"+minAlpha+",\"alpha_max\":"+maxAlpha+",\"deterministic\":true,\"lifetime\":[0,90],\"bounds\":["+bounds+"],\"bound_note\":\"Conservative billboard bounds; visible alpha silhouette lies inside these bounds\"}";
  Files.writeString(Path.of(args[0]),result);System.out.println(result);
 }
}
