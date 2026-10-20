package skyhammer.aircraft;
import java.io.DataInputStream;
import java.io.InputStream;
import java.lang.reflect.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import java.nio.file.*;
import viewpoint.render.FrameContext;

/**
 * Decides whether the 3D renderer may run with the installed Viewpoint.
 * Instead of pinning one Viewpoint jar, it checks that everything this jar uses from Viewpoint still
 * exists with the same signature: every viewpoint.* field / method / constructor referenced from our
 * classes (read from their constant pools), plus the two methods our @Patch classes hook. A Viewpoint
 * update that keeps those keeps the renderer on; one that changes them switches it off with a fault.
 */
public final class Main {
    public static volatile boolean supported;
    // methods hooked by name through @Patch (not visible in the constant pool)
    private static final String[][] PATCH_TARGETS = {
        {"viewpoint/render/ModelPass", "gbuffer", "(Lviewpoint/render/FrameContext;)V"},
        {"viewpoint/input/FreeCam", "view", "(Lviewpoint/core/Frame;FFF[F[F)Z"},
        {"viewpoint/render/FrameUniforms", "set", "(Lviewpoint/render/FrameContext;Lviewpoint/render/Targets;)V"},
        {"viewpoint/render/WorldRenderer", "drawTranslucent", "(Lviewpoint/render/SceneData;)V"},
    };

    public static void main(String[] args) {
        try {
            Path vpJar=Path.of(FrameContext.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            ClassLoader vp=FrameContext.class.getClassLoader();
            Set<String> refs=new TreeSet<>();
            Path ours=Path.of(Main.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            try(ZipFile z=new ZipFile(ours.toFile())) {
                for(Enumeration<? extends ZipEntry> e=z.entries(); e.hasMoreElements();) {
                    ZipEntry en=e.nextElement();
                    if(en.getName().endsWith(".class"))
                        try(InputStream in=z.getInputStream(en)) { viewpointRefs(new DataInputStream(in), refs); }
                }
            }
            for(String[] t:PATCH_TARGETS) refs.add(t[0]+"|"+t[1]+"|"+t[2]);
            List<String> missing=new ArrayList<>();
            for(String r:refs) if(!exists(vp, r)) missing.add(r.replace('|', ' '));
            supported=missing.isEmpty();
            if(!supported)AircraftBridge.fault="Viewpoint changed what Skyhammer uses: "+String.join(", ", missing.subList(0, Math.min(4, missing.size())));
            System.out.println("[SkyhammerAircraft] 0.9.7 loaded; Viewpoint jar "+sha(vpJar).substring(0, 12)+", "
                    +refs.size()+" Viewpoint members checked, "+missing.size()+" missing; supported Viewpoint="+supported);
            for(String m:missing) System.out.println("[SkyhammerAircraft]   missing in Viewpoint: "+m);
        } catch(Throwable e) {
            supported=false;
            AircraftBridge.fault="Cannot verify Viewpoint: "+e;
            System.err.println("[SkyhammerAircraft] "+AircraftBridge.fault);
        }
    }

    /** adds "owner|name|descriptor" for every Fieldref/Methodref/InterfaceMethodref into viewpoint/ */
    static void viewpointRefs(DataInputStream in, Set<String> out) throws Exception {
        in.readInt(); in.readUnsignedShort(); in.readUnsignedShort();
        int n=in.readUnsignedShort();
        String[] utf=new String[n]; int[] classIdx=new int[n]; int[][] ref=new int[n][]; int[][] nat=new int[n][];
        for(int i=1;i<n;i++) {
            int tag=in.readUnsignedByte();
            switch(tag) {
                case 1 -> utf[i]=in.readUTF();
                case 3, 4 -> in.readInt();
                case 5, 6 -> { in.readLong(); i++; }
                case 7 -> classIdx[i]=in.readUnsignedShort();
                case 8, 16, 19, 20 -> in.readUnsignedShort();
                case 9, 10, 11 -> ref[i]=new int[]{in.readUnsignedShort(), in.readUnsignedShort()};
                case 12 -> nat[i]=new int[]{in.readUnsignedShort(), in.readUnsignedShort()};
                case 15 -> { in.readUnsignedByte(); in.readUnsignedShort(); }
                case 17, 18 -> in.readInt();
                default -> throw new IllegalStateException("constant pool tag "+tag);
            }
        }
        for(int i=1;i<n;i++) if(ref[i]!=null) {
            String owner=utf[classIdx[ref[i][0]]];
            if(owner==null||!owner.startsWith("viewpoint/")) continue;
            int[] nt=nat[ref[i][1]];
            out.add(owner+"|"+utf[nt[0]]+"|"+utf[nt[1]]);
        }
    }

    /** true if owner (or a supertype) declares name with exactly this descriptor */
    static boolean exists(ClassLoader cl, String r) {
        String[] p=r.split("\\|");
        Class<?> c;
        try { c=Class.forName(p[0].replace('/', '.'), false, cl); } catch(Throwable t) { return false; }
        boolean field=!p[2].startsWith("(");
        Deque<Class<?>> todo=new ArrayDeque<>(); todo.add(c);
        while(!todo.isEmpty()) {
            Class<?> k=todo.poll();
            try {
                if(field) { for(Field f:k.getDeclaredFields()) if(f.getName().equals(p[1])&&desc(f.getType()).equals(p[2])) return true; }
                else if(p[1].equals("<init>")) { if(k==c) for(Constructor<?> m:k.getDeclaredConstructors()) if(desc(m.getParameterTypes(), void.class).equals(p[2])) return true; }
                else for(Method m:k.getDeclaredMethods()) if(m.getName().equals(p[1])&&desc(m.getParameterTypes(), m.getReturnType()).equals(p[2])) return true;
            } catch(Throwable t) { return false; }
            if(k.getSuperclass()!=null) todo.add(k.getSuperclass());
            todo.addAll(Arrays.asList(k.getInterfaces()));
        }
        return false;
    }

    static String desc(Class<?>[] params, Class<?> ret) {
        StringBuilder b=new StringBuilder("(");
        for(Class<?> p:params) b.append(desc(p));
        return b.append(')').append(desc(ret)).toString();
    }

    static String desc(Class<?> t) {
        if(t.isArray()) return t.getName().replace('.', '/');
        if(t==void.class) return "V"; if(t==boolean.class) return "Z"; if(t==byte.class) return "B";
        if(t==char.class) return "C"; if(t==short.class) return "S"; if(t==int.class) return "I";
        if(t==long.class) return "J"; if(t==float.class) return "F"; if(t==double.class) return "D";
        return "L"+t.getName().replace('.', '/')+";";
    }

    static String sha(Path p) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=Files.newInputStream(p)) {
            byte[] block=new byte[65536]; int n;
            while((n=in.read(block))>0)digest.update(block,0,n);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
}
