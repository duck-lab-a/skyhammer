package skyhammer.aircraft;

/** Pure, saved-combat-clock A-10 pose. Tile XY is deliberately independent of pitch/bank. */
public final class Strafer {
    public static final double DURATION=14, CENTER_TIME=7.6, SPEED=50;
    public static final double GUN_X=-.18,GUN_Y=-.46,GUN_Z=7.56;
    public record Pose(boolean visible,double x,double y,double height,double yaw,
                       double pitch,double bank,boolean firing,double spin,double elapsed) {}
    private Strafer() {}
    public static double releaseTime(int i){return 5.6+.3*i;}
    public static final double[] RACK_X={-4.65,-3.35,3.35,4.65};
    public record Canister(boolean visible,boolean attached,double x,double y,double height,double yaw,double pitch,double roll) {}
    public static Pose napalmPose(double e,double x,double y,double floor,double heading,double len,double altitude){
        Pose base=pose(e,x,y,floor,heading,len,altitude);
        if(!base.visible())return base;
        double a=clamp(altitude,30,150),down=smooth((e-3.5)/3),up=smooth((e-6.5)/7.5);
        double h=a-12*down+(a*.25+160)*up;
        double pitch=Math.toRadians(7.5)*smooth((e-3.5)/1.5)*(1-smooth((e-6.5)/1.2))-
            Math.toRadians(28)*smooth((e-6.5)/2);
        return new Pose(true,base.x(),base.y(),floor*Projection.STOREY+h,base.yaw(),pitch,
            Math.toRadians(35)*smooth((e-7.2)/2),false,0,e);
    }
    public static Canister canister(double e,int index,double x,double y,double floor,double heading,double len,double altitude,double scale){
        if(index<0||index>3)throw new IllegalArgumentException("rack index");
        double release=releaseTime(index),t=(e-release)/.6;
        Pose p=napalmPose(Math.min(e,release),x,y,floor,heading,len,altitude);
        if(!p.visible()||t>=1)return new Canister(false,false,0,0,0,0,0,0);
        double lx=RACK_X[index]*scale,ly=-1.05*scale,lz=-.36*scale;
        double ry=ly*Math.cos(p.pitch())-lz*Math.sin(p.pitch());
        double rz=ly*Math.sin(p.pitch())+lz*Math.cos(p.pitch());
        double wx=lx*Math.cos(p.yaw())+rz*Math.sin(p.yaw());
        double wz=-lx*Math.sin(p.yaw())+rz*Math.cos(p.yaw());
        double sx=p.x()-wx,sy=p.y()-wz,sh=p.height()+ry;
        if(t<0)return new Canister(true,true,sx,sy,sh,p.yaw(),p.pitch(),0);
        // S is the existing e=6.0 impact point, not the aircraft's e=6.0 position.
        double along=index*len/3,ex=x+Math.cos(heading)*along,ey=y+Math.sin(heading)*along;
        double h=sh+(floor*Projection.STOREY-sh)*(t*t*.6+t*.4);
        return new Canister(true,false,sx+(ex-sx)*t,sy+(ey-sy)*t,h,p.yaw(),p.pitch()+t*1.7,t*2.2);
    }
    static double clamp(double x,double lo,double hi){return Math.max(lo,Math.min(hi,x));}
    static double smooth(double t){t=clamp(t,0,1);return t*t*(3-2*t);}
    public static double targetAlong(double e,double len){return clamp((e-6)/1.5,0,1)*len;}
    public static double aboveGround(double e,double altitude){
        double a=clamp(altitude,30,150);
        if(e<=5)return a;
        if(e<=7.6)return a*(1-.45*smooth((e-5)/2.6));
        return .55*a+(a*.45+180)*smooth((e-7.6)/6.4);
    }
    private static double aim(double e,double len,double altitude){
        return Math.atan2(aboveGround(e,altitude),targetAlong(e,len)-(e-CENTER_TIME)*SPEED);
    }
    public static Pose pose(double e,double x,double y,double floor,double heading,double len,double altitude){
        if(!Double.isFinite(e+x+y+floor+heading+len+altitude)||e<0||e>=DURATION||len<=0)
            return new Pose(false,0,0,0,0,0,0,false,0,e);
        double d=(e-CENTER_TIME)*SPEED, pitch,bank=0;
        if(e<5)pitch=aim(5,len,altitude)*smooth((e-4.4)/.6);
        else if(e<=6.5)pitch=aim(e,len,altitude);
        else if(e<=7.6)pitch=aim(6.5,len,altitude)*(1-smooth((e-6.5)/1.1));
        else {
            double t=clamp((e-7.6)/6.4,0,1);
            double climb=(clamp(altitude,30,150)*.45+180)*6*t*(1-t)/6.4;
            pitch=-Math.atan2(climb,SPEED);
            bank=Math.toRadians(58)*smooth((e-7.6)/1.9);
        }
        boolean fire=e>=5&&e<=6.5;
        double spin=clamp(e-5,0,1.5)*(2*Math.PI*9.3);
        return new Pose(true,x+Math.cos(heading)*d,y+Math.sin(heading)*d,
            floor*Projection.STOREY+aboveGround(e,altitude),
            Math.atan2(-Math.cos(heading),-Math.sin(heading)),pitch,bank,fire,spin,e);
    }
}
