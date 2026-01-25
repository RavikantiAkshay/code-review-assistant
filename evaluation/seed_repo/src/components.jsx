// React component with hooks and security issues
// ISSUE COUNT: 7 issues

import React, { useState, useEffect } from 'react';

// Issue 1: Function component with issues
function UserProfile(props) {
    // Issue 2: Missing dependency in useEffect (CORRECTNESS - HIGH)
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`/api/users/${props.userId}`)
            .then(res => res.json())
            .then(data => {
                setUser(data);
                setLoading(false);
            });
    }, []); // Missing props.userId in dependency array!

    // Issue 3: Conditional hook call (CORRECTNESS - HIGH)
    if (loading) {
        const [temp, setTemp] = useState(0); // Hooks called conditionally!
        return <div>Loading...</div>;
    }

    // Issue 4: dangerouslySetInnerHTML (SECURITY - HIGH)
    const renderBio = () => {
        return <div dangerouslySetInnerHTML={{ __html: user.bio }} />;
    };

    // Issue 5: Inline function in render (COMPLEXITY - LOW)
    return (
        <div>
            <h1>{user.name}</h1>
            {renderBio()}
            {/* Issue 6: onClick with inline function creates new function each render */}
            <button onClick={() => console.log(user)}>
                Log User
            </button>
            {/* Issue 7: Key prop missing in list */}
            <ul>
                {user.posts && user.posts.map((post) => (
                    <li>{post.title}</li>
                ))}
            </ul>
        </div>
    );
}

export default UserProfile;
