package skyhammer.aircraft;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** Procedural visual prototype. Metres, Y up; no game state or damage logic. */
public final class Nuke {
    public static final double FIREBALL=50, SHOCK_SPEED=120, SHOCK_MAX=300, CLOUD_LIFE=90;
    public record Puff(float x,float y,float z,float rx,float ry,float angle,int tile,
                       float r,float g,float b,float alpha,float emissive) {}
    private static double clamp(double x){return Math.max(0,Math.min(1,x));}
    private static double smooth(double x){x=clamp(x);return x*x*(3-2*x);}
    private static void add(List<Puff> a,double x,double y,double z,double rx,double ry,double angle,
                            int tile,double r,double g,double b,double alpha,double glow,double size){
        if(alpha<.001||rx<.001||ry<.001)return;
        a.add(new Puff((float)(x*size),(float)(y*size),(float)(z*size),(float)(rx*size),
            (float)(ry*size),(float)angle,tile,(float)r,(float)g,(float)b,(float)alpha,(float)glow));
    }
    public static List<Puff> sample(double e,double size){
        return sample(e,size,true);
    }
    public static List<Puff> sample(double e,double size,boolean includeShock){
        ArrayList<Puff> out=new ArrayList<>(520);
        if(!Double.isFinite(e)||!Double.isFinite(size)||e<0||e>=CLOUD_LIFE)return out;
        size=Math.max(.5,Math.min(1.5,size));
        Random rng=new Random(610017L);
        double growth=smooth((e-.7)/7.3), rise=270*growth+24*smooth((e-8)/52);
        double expand=1+.13*smooth((e-8)/52), fade=smooth((90-e)/30);
        double drift=Math.max(0,e-8)*.20;
        double heat=1-smooth((e-1.8)/6.2);
        // Continuous rising column; small overlapping wisps suppress a stack-of-spheres silhouette.
        for(int i=0;i<132;i++){
            double h=(i+.5)/132., a=rng.nextDouble()*Math.PI*2+e*.018;
            double rr=(6+13*Math.sin(h*Math.PI))*rng.nextDouble();
            double r=(13+10*rng.nextDouble()+7*h)*(.35+.65*growth);
            double alpha=growth*fade*(.48+.35*rng.nextDouble());
            double warmth=heat*Math.pow(h,2);
            add(out,Math.cos(a)*rr+drift*h+7*Math.sin(h*9+e*.025)*growth,h*rise,Math.sin(a)*rr+5*Math.sin(h*12)*growth,r,r*(1.0+rng.nextDouble()*.5),
                rng.nextDouble()*6.28,i%8,.43+.30*warmth,.41-.16*warmth,.37-.25*warmth,
                alpha,.22*warmth,size);
        }
        // Overturning torus: particles travel over the crown and down its outer edge.
        for(int i=0;i<128;i++){
            double a=2*Math.PI*(i%32)/32+rng.nextDouble()*.12+e*.009;
            double roll=(i/32)*Math.PI*.5+rng.nextDouble()*.65-e*.065;
            double major=58*growth*expand, minor=18*growth;
            double rr=major+Math.cos(roll)*minor;
            double y=rise+Math.sin(roll)*minor;
            double r=(23+11*rng.nextDouble())*growth*expand;
            double outer=(rr/100), localFade=smooth((90-e-outer*8)/25);
            double warmth=heat*(.4+.6*Math.max(0,-Math.sin(roll)));
            double top=.5+.5*Math.sin(roll);
            add(out,Math.cos(a)*rr+drift,y,Math.sin(a)*rr,r*1.13,r*(.58+rng.nextDouble()*.2),
                rng.nextDouble()*6.28,i%8,.55+.18*top+.25*warmth,.53+.17*top-.14*warmth,
                .48+.17*top-.32*warmth,localFade*growth*.86,.42*warmth,size);
        }
        // Broad crown closes the central opening without a perfectly spherical dome.
        for(int i=0;i<64;i++){
            double a=rng.nextDouble()*6.28+e*.009, rr=Math.sqrt(rng.nextDouble())*66*growth*expand;
            double h=Math.sqrt(Math.max(0,1-rr*rr/(78*78*expand*expand)))*23*growth;
            double r=(18+12*rng.nextDouble())*growth*expand;
            double localFade=smooth((90-e-(rr/100)*8)/25);
            add(out,Math.cos(a)*rr+drift,rise+h,Math.sin(a)*rr,r*1.10,r*.70,
                rng.nextDouble()*6.28,i%8,.76+.20*heat,.73-.15*heat,.66-.40*heat,
                localFade*growth*.8,.35*heat,size);
        }
        // Dust drawn up from the ground; low, irregular skirt.
        for(int i=0;i<70;i++){
            double a=rng.nextDouble()*6.28,rr=Math.sqrt(rng.nextDouble())*(55+e*.35);
            double r=12+15*rng.nextDouble();
            add(out,Math.cos(a)*rr,4+rng.nextDouble()*13,Math.sin(a)*rr,r,r*.65,
                rng.nextDouble()*6.28,i%8,.44,.40,.34,smooth((e-.35)/1.2)*fade*.55,0,size);
        }
        // Incandescent hemisphere, followed by the hot ascending core.
        double fireAlpha=(1-smooth((e-1.3)/2.3));
        double radius=FIREBALL*Math.pow(smooth(e/.85),.4);
        for(int i=0;i<64;i++){
            double a=rng.nextDouble()*6.28, h=rng.nextDouble(),r=radius*(.28+.16*rng.nextDouble());
            double radial=Math.sqrt(1-h*h)*radius*.70;
            double hot=1-smooth(e/3.6), flash=1-smooth(e/1.2);
            add(out,Math.cos(a)*radial,h*radius*.72+rise*.27,Math.sin(a)*radial,r,r,
                rng.nextDouble()*6.28,i%8,1,.27+.57*hot+.16*flash,.035+.28*hot+.68*flash,
                fireAlpha,.68+.32*flash,size);
        }
        // Radius is a timing contract: visual size MUST NOT multiply shock propagation.
        double shock=SHOCK_SPEED*e;
        if(includeShock&&shock<SHOCK_MAX){
            double af=smooth(e/.08)*(1-smooth((shock-255)/45));
            for(int i=0;i<112;i++){
                double a=2*Math.PI*i/112,r=7+9*rng.nextDouble();
                // Compensate size so the leading ring stays at 120 metres/second.
                add(out,Math.cos(a)*shock/size,3+rng.nextDouble()*5,Math.sin(a)*shock/size,
                    r,r*.55,rng.nextDouble()*6.28,i%8,.64,.48,.29,af*.54,.08,size);
                if(i%5==0)add(out,Math.cos(a)*shock/size,3,Math.sin(a)*shock/size,
                    2,4,a,i%8,1,.32,.04,af*.8,1,size);
            }
        }
        return out;
    }
}
