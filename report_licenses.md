# License Report: Programming Language Repositories on GitHub

Date: 2026-08-20
Source: GitHub API (`repos/{owner}/{repo}` and `repos/{owner}/{repo}/license`)

## Summary Table

| Language | Repository | License | Type |
|---|---|---|---|
| Python | python/cpython | PSF License Agreement (PSF-2.0) | Permissive, custom |
| Go | golang/go | BSD 3-Clause | Permissive |
| Rust | rust-lang/rust | Apache 2.0 OR MIT (dual) | Permissive |
| Java (OpenJDK) | openjdk/jdk | GPL v2 with Classpath Exception | Copyleft, with exception |
| Ruby | ruby/ruby | Ruby License OR 2-clause BSD (dual) | Permissive, custom |
| PHP | php/php-src | PHP License 3.01 (BSD-style) | Permissive |
| Node.js (JavaScript) | nodejs/node | MIT, with mixed bundled components | Permissive |
| Kotlin | JetBrains/kotlin | Apache 2.0 | Permissive |
| Swift | swiftlang/swift | Apache 2.0 with Runtime Library Exception | Permissive |
| Zig | ziglang/zig | MIT | Permissive |

## Analysis for Each Repository

### CPython (python/cpython)
The GitHub API reports the license as "Other" (NOASSERTION). The `LICENSE`
file contains the history of the project and a stack of agreements: the PSF
License Agreement (the primary license), plus the older BeOpen, CNRI, and CWI
agreements. The PSF license is permissive and is compatible with the GPL. You
can use, change, and distribute Python without a requirement to release your
source code. You must keep the copyright notices.

### Go (golang/go)
The license is BSD 3-Clause. This is a simple permissive license. You can
use, change, and sell the software. You must keep the copyright notice, and
you must not use the Google name to promote your product. A separate patent
grant file (`PATENTS`) gives protection against patent claims from Google.

### Rust (rust-lang/rust)
Rust uses a dual license: Apache 2.0 or MIT, at your selection. The GitHub
API shows only Apache 2.0 because it detects one file. This dual model is the
standard in the Rust ecosystem. Apache 2.0 gives an explicit patent grant.
The MIT option keeps compatibility with GPL v2 projects.

### OpenJDK (openjdk/jdk)
The license is GPL v2 with the Classpath Exception. This is the only strong
copyleft license in this set. Changes to the JDK itself must stay under GPL
v2. The Classpath Exception is important: programs that only link to the
class libraries do not become GPL. Because of this exception, you can run
and ship commercial Java applications on OpenJDK.

### Ruby (ruby/ruby)
The GitHub API reports "Other" (NOASSERTION). The `COPYING` file gives a dual
license: the custom Ruby License or the 2-clause BSD License, at your
selection. The Ruby License is permissive, but it has special conditions for
modified versions (for example, a requirement to use a different name for
non-standard binaries). Most users select the BSD option because it is
simpler.

### PHP (php/php-src)
The GitHub API detects BSD 3-Clause. Since PHP 8.3 the project moved from the
old PHP License 3.01 to a modified BSD 3-Clause license. It is permissive.
One clause controls the use of the name "PHP" in derived products.

### Node.js (nodejs/node)
The GitHub API reports "Other" (NOASSERTION). The core Node.js code is under
the MIT license. The `LICENSE` file also lists the licenses of many bundled
components: V8 (BSD), libuv (MIT), OpenSSL (Apache 2.0), ICU (Unicode
license), and others. All the bundled licenses are permissive, but a full
compliance review must include each component notice.

### Kotlin (JetBrains/kotlin)
The GitHub API reports no license because the file is in the non-standard
path `license/LICENSE.txt`. That file is the Apache License 2.0. The
`license/third_party` directory lists the licenses of bundled third-party
code. In effect, Kotlin is a standard Apache 2.0 project.

### Swift (swiftlang/swift)
The license is Apache 2.0 with a Runtime Library Exception. The exception
removes the Apache attribution requirement for binaries that only include the
compiled runtime libraries. Because of this, applications built with Swift do
not need to show Swift license notices.

### Zig (ziglang/zig)
The license is MIT, the most simple permissive license in this set. Note:
the repository description says "Moved to Codeberg" — the GitHub repository
is now a mirror, and primary development occurs on Codeberg. The license is
the same there.

## Conclusions

1. Permissive licenses are the standard for programming language
   implementations. Nine of the ten projects are permissive; only OpenJDK
   uses copyleft, and its Classpath Exception removes most of the copyleft
   effect for users.
2. The GitHub license detector is not sufficient for a compliance decision.
   It reported "Other" or nothing for four of the ten repositories
   (CPython, Ruby, Node.js, Kotlin). A manual read of the license files was
   necessary in each of those cases.
3. Dual licensing (Rust, Ruby) and license exceptions (OpenJDK, Swift) are
   frequent patterns. The exceptions exist for one reason: to make sure that
   programs built with the language do not inherit license obligations.
4. Large projects such as Node.js and Kotlin bundle third-party code with
   its own licenses. A compliance review of these projects must include the
   third-party notices, not only the top-level license file.
