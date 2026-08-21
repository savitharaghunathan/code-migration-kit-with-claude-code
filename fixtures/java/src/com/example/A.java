// SPDX-License-Identifier: Apache-2.0
package com.example;

import java.util.List;              // JDK stdlib: must NOT appear as an edge
import com.example.B;               // in-repo: edge A.java -> B.java
import com.example.util.Helper;     // in-repo: edge A.java -> Helper.java

public class A {
    public String run() {
        return List.of(new B().value(), Helper.format("ok")).toString();
    }
}
