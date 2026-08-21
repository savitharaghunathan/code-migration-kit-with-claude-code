// SPDX-License-Identifier: Apache-2.0
package com.example.util;

import java.util.Objects;  // JDK stdlib: must NOT appear as an edge

public class Helper {
    public static String format(String s) {
        return Objects.requireNonNull(s).trim();
    }
}
