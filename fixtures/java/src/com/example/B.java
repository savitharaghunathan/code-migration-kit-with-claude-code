// SPDX-License-Identifier: Apache-2.0
package com.example;

import org.slf4j.Logger;  // third-party: must NOT appear as an edge (never compiled, only parsed)
import com.example.C;     // in-repo: edge B.java -> C.java

public class B {
    public int value() {
        return new C().compute();
    }
}
