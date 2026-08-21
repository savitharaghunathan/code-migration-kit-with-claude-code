// SPDX-License-Identifier: Apache-2.0
using System;  // stdlib: must NOT appear as an edge

namespace Example.Util;

public static class Helper
{
    public static string Format(string s)
    {
        return s?.Trim() ?? throw new ArgumentNullException(nameof(s));
    }
}
