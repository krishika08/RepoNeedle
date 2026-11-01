package com.reponeedle.fixtures;

// 1. Package imports
import java.util.List;
import java.util.ArrayList;
import java.util.Map;

// 2. Static imports
import static java.lang.Math.max;
import static java.lang.Math.min;

// 5. Interface implementations
interface TaskExecutor {
    void execute();

    int getStatusCode();
}

// 4. Inheritance
abstract class AbstractBaseService {
    public void commonSetup() {
        System.out.println("setup");
    }

    public abstract void doWork();
}

public class JavaParserFixture extends AbstractBaseService implements TaskExecutor {

    private int status = 200;

    // 3. Overloaded methods
    public String renderData(String text) {
        return "text:" + text;
    }

    public String renderData(int number) {
        return "num:" + number;
    }

    public String renderData(String text, boolean uppercase) {
        return uppercase ? text.toUpperCase() : text;
    }

    // Interface implementation
    @Override
    public void execute() {
        commonSetup(); // Inherited method call
        doWork();
    }

    @Override
    public int getStatusCode() {
        return this.status;
    }

    @Override
    public void doWork() {
        // Internal work
    }

    // Callers:

    // 1 & 2. Package and static import calls
    public int callerStaticAndPackageImports(int a, int b) {
        List<String> list = new ArrayList<>();
        list.add("item");
        int highest = max(a, b);
        int lowest = min(a, b);
        return highest - lowest;
    }

    // 3. Overloaded method calls
    public void callerOverloadedMethods() {
        String s1 = renderData("hello");
        String s2 = renderData(123);
        String s3 = renderData("world", true);
    }

    // 4. Inheritance call
    public void callerInheritedMethod() {
        commonSetup(); // Defined in AbstractBaseService
    }

    // 5. Interface polymorphism
    public void callerInterfacePolymorphism(TaskExecutor executor) {
        executor.execute();
        int code = executor.getStatusCode();
    }
}
